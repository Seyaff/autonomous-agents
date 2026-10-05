"""
Dine-in staff and tables. The owner manages staff from the dashboard. Waiters, reception and kitchen
use their own sign-in on the iPad or the shared screens, with a token separate from the owner's.
"""

from typing import List, Optional

from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from core.database import get_database
from core.settings import settings
from middlewares.auth_middleware import require_owner
from services import staff as svc
from services.staff import SHIFT_HOURS, StaffError

# Owner: staff and table setup, under the owner's tenant.
owner_staff_routes = APIRouter(prefix="/tenant/current", tags=["Staff"])

# Staff: the iPad and the shared screens.
staff_routes = APIRouter(prefix="/staff", tags=["Staff"])

STAFF_COOKIE = "staff_token"
# A linked iPad keeps a device cookie for a year. It names the one restaurant the iPad belongs to.
DEVICE_COOKIE = "staff_device"
DEVICE_TYPE = "staff_device"
DEVICE_DAYS = 365
# A plain marker the page can read, so the owner dashboard can send a linked iPad back to its staff screen.
DEVICE_MARK = "siyaf_ipad"


def _device_tenant(request: Request):
    token = request.cookies.get(DEVICE_COOKIE)
    if not token:
        return None
    try:
        claims = jwt.decode(token, key=settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None
    return claims.get("tid") if claims.get("type") == DEVICE_TYPE else None


def _require_linked(request: Request, tenant_id: str) -> None:
    if _device_tenant(request) != tenant_id:
        raise HTTPException(status_code=403, detail="This iPad isn't linked to this restaurant. Enter the restaurant code.")


def _fail(e: StaffError):
    return HTTPException(status_code=400, detail=str(e))


async def _tenant_id_for(db, slug: str) -> str:
    tenant = await db.tenants.find_one({"tenant_slug": slug}, {"tenant_id": 1})
    if not tenant:
        raise HTTPException(status_code=404, detail="Restaurant not found.")
    return tenant["tenant_id"]


async def current_staff(request: Request, db=Depends(get_database)) -> dict:
    token = request.cookies.get(STAFF_COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="Sign in with your PIN first.")
    try:
        return await svc.staff_from_token(db, token)
    except StaffError as e:
        raise HTTPException(status_code=401, detail=str(e))


def staff_with(*roles: str):
    async def dependency(staff: dict = Depends(current_staff)) -> dict:
        if staff.get("role") not in roles:
            raise HTTPException(status_code=403, detail="Your role can't do that.")
        return staff
    return dependency


def _tenant_of(staff: dict) -> str:
    return staff["tenant_id"]


# ---------------------------------------------------------------------------
# Owner
# ---------------------------------------------------------------------------
class StaffCreate(BaseModel):
    name: str = Field(max_length=40)
    role: str
    pin: str = Field(min_length=4, max_length=4)


class PinBody(BaseModel):
    pin: str = Field(min_length=4, max_length=4)


class TableCountBody(BaseModel):
    count: int


def _owner_tenant(current_user: dict) -> str:
    tenant_id = current_user.get("active_tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="No active tenant found.")
    return tenant_id


@owner_staff_routes.get("/staff")
async def owner_list_staff(db=Depends(get_database), current_user: dict = Depends(require_owner)):
    tenant_id = _owner_tenant(current_user)
    tenant = await db.tenants.find_one({"tenant_id": tenant_id}, {"dine_table_count": 1}) or {}
    return {"staff": await svc.list_staff(db, tenant_id), "table_count": int(tenant.get("dine_table_count") or 0)}


@owner_staff_routes.post("/staff", status_code=201)
async def owner_add_staff(payload: StaffCreate, db=Depends(get_database), current_user: dict = Depends(require_owner)):
    try:
        return await svc.create_staff(db, _owner_tenant(current_user), payload.name, payload.role, payload.pin)
    except StaffError as e:
        raise _fail(e)


@owner_staff_routes.post("/staff/{staff_id}/reset-pin")
async def owner_reset_pin(staff_id: str, payload: PinBody, db=Depends(get_database), current_user: dict = Depends(require_owner)):
    try:
        return await svc.reset_pin(db, _owner_tenant(current_user), staff_id, payload.pin)
    except StaffError as e:
        raise _fail(e)


@owner_staff_routes.post("/staff/{staff_id}/unlock")
async def owner_unlock(staff_id: str, db=Depends(get_database), current_user: dict = Depends(require_owner)):
    try:
        return await svc.unlock(db, _owner_tenant(current_user), staff_id)
    except StaffError as e:
        raise _fail(e)


@owner_staff_routes.post("/staff/{staff_id}/remove")
async def owner_remove(staff_id: str, db=Depends(get_database), current_user: dict = Depends(require_owner)):
    try:
        await svc.remove(db, _owner_tenant(current_user), staff_id)
    except StaffError as e:
        raise _fail(e)
    return {"status": "removed"}


@owner_staff_routes.get("/staff-code")
async def owner_get_staff_code(db=Depends(get_database), current_user: dict = Depends(require_owner)):
    return {"code": await svc.get_access_code(db, _owner_tenant(current_user))}


@owner_staff_routes.post("/staff-code/rotate")
async def owner_rotate_staff_code(db=Depends(get_database), current_user: dict = Depends(require_owner)):
    return {"code": await svc.rotate_access_code(db, _owner_tenant(current_user))}


@owner_staff_routes.put("/dine-tables/count")
async def owner_set_tables(payload: TableCountBody, db=Depends(get_database), current_user: dict = Depends(require_owner)):
    try:
        return {"count": await svc.set_table_count(db, _owner_tenant(current_user), payload.count)}
    except StaffError as e:
        raise _fail(e)


# ---------------------------------------------------------------------------
# Staff sign-in
# ---------------------------------------------------------------------------
class LinkBody(BaseModel):
    restaurant: str = Field(min_length=1, max_length=80)
    code: str = Field(min_length=6, max_length=6)


class SignInBody(BaseModel):
    restaurant: str = Field(min_length=1, max_length=80)
    staff_id: str
    pin: str = Field(min_length=4, max_length=4)
    device: Optional[str] = Field(default="iPad", max_length=40)


@staff_routes.post("/link")
async def staff_link(payload: LinkBody, response: Response, db=Depends(get_database)):
    """Links this iPad to one restaurant, using the code the owner shows on the Staff page."""
    tenant_id = await _tenant_id_for(db, payload.restaurant)
    tenant = await db.tenants.find_one({"tenant_id": tenant_id}, {"staff_access_code": 1, "tenant_slug": 1}) or {}
    if not svc.check_access_code(tenant.get("staff_access_code"), payload.code):
        raise HTTPException(status_code=403, detail="That code isn't right. Ask the owner for the code on the Staff page.")
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {"tid": tenant_id, "type": DEVICE_TYPE, "iat": now, "exp": now + timedelta(days=DEVICE_DAYS)},
        key=settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    max_age = DEVICE_DAYS * 86400
    response.set_cookie(DEVICE_COOKIE, token, max_age=max_age, httponly=True, secure=True, samesite="lax", path="/")
    response.set_cookie(DEVICE_MARK, tenant.get("tenant_slug") or payload.restaurant, max_age=max_age, secure=True, samesite="lax", path="/")
    return {"linked": True}


@staff_routes.get("/roster")
async def staff_roster(restaurant: str, request: Request, db=Depends(get_database)):
    """Names for the sign-in list, with role and lock state. No PINs. Only on an iPad linked to this restaurant."""
    tenant_id = await _tenant_id_for(db, restaurant)
    _require_linked(request, tenant_id)
    return {"waiters": await svc.roster(db, tenant_id)}


@staff_routes.post("/sign-in")
async def staff_sign_in(payload: SignInBody, request: Request, response: Response, db=Depends(get_database)):
    tenant_id = await _tenant_id_for(db, payload.restaurant)
    _require_linked(request, tenant_id)
    try:
        result = await svc.sign_in(db, tenant_id, payload.staff_id, payload.pin, payload.device or "iPad")
    except StaffError as e:
        raise _fail(e)
    response.set_cookie(
        STAFF_COOKIE, result["token"], max_age=SHIFT_HOURS * 3600,
        httponly=True, secure=True, samesite="lax", path="/",
    )
    # A waiter's iPad must not also hold an owner's sign-in, or the waiter could open the dashboard.
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/api/auth")
    return {"staff": result["staff"]}


@staff_routes.post("/sign-out")
async def staff_sign_out(response: Response, staff: dict = Depends(current_staff), db=Depends(get_database)):
    await svc.sign_out(db, _tenant_of(staff), staff["staff_id"])
    response.delete_cookie(STAFF_COOKIE, path="/")
    return {"status": "signed out"}


@staff_routes.get("/me")
async def staff_me(staff: dict = Depends(current_staff)):
    return svc.public_staff(staff)


# ---------------------------------------------------------------------------
# Tables and orders
# ---------------------------------------------------------------------------
class OrderLine(BaseModel):
    name: str = Field(max_length=120)
    qty: int


class OrderBody(BaseModel):
    table_no: int
    items: List[OrderLine]


class KitchenBody(BaseModel):
    status: str


@staff_routes.get("/menu")
async def staff_menu(staff: dict = Depends(staff_with("waiter")), db=Depends(get_database)):
    tenant = await db.tenants.find_one({"tenant_id": _tenant_of(staff)}) or {}
    return {"items": await svc.staff_menu(db, _tenant_of(staff), tenant)}


@staff_routes.get("/tables")
async def staff_tables(staff: dict = Depends(current_staff), db=Depends(get_database)):
    return {"tables": await svc.table_board(db, _tenant_of(staff))}


@staff_routes.get("/orders")
async def staff_orders(staff: dict = Depends(staff_with("reception", "kitchen", "waiter")), db=Depends(get_database)):
    return {"orders": await svc.open_orders(db, _tenant_of(staff))}


@staff_routes.post("/orders", status_code=201)
async def staff_send_order(payload: OrderBody, staff: dict = Depends(staff_with("waiter")), db=Depends(get_database)):
    try:
        return await svc.send_order(
            db, _tenant_of(staff), staff, payload.table_no,
            [{"name": i.name, "qty": i.qty} for i in payload.items],
        )
    except StaffError as e:
        raise _fail(e)


@staff_routes.post("/orders/{order_id}/kitchen")
async def staff_kitchen(order_id: str, payload: KitchenBody, staff: dict = Depends(staff_with("kitchen")), db=Depends(get_database)):
    try:
        return await svc.kitchen_update(db, _tenant_of(staff), staff, order_id, payload.status)
    except StaffError as e:
        raise _fail(e)


@staff_routes.post("/orders/{order_id}/served")
async def staff_served(order_id: str, staff: dict = Depends(staff_with("waiter")), db=Depends(get_database)):
    try:
        return await svc.mark_served(db, _tenant_of(staff), staff, order_id)
    except StaffError as e:
        raise _fail(e)


@staff_routes.post("/tables/{table_no}/bill")
async def staff_bill(table_no: int, staff: dict = Depends(staff_with("waiter")), db=Depends(get_database)):
    try:
        return await svc.request_bill(db, _tenant_of(staff), staff, table_no)
    except StaffError as e:
        raise _fail(e)


@staff_routes.post("/tables/{table_no}/paid")
async def staff_paid(table_no: int, staff: dict = Depends(staff_with("waiter")), db=Depends(get_database)):
    try:
        return await svc.mark_paid_cash(db, _tenant_of(staff), staff, table_no)
    except StaffError as e:
        raise _fail(e)
