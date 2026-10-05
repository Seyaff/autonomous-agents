"""
Dine-in staff and tables. The owner manages staff from the dashboard. Waiters, reception and kitchen
use their own sign-in on the iPad or the shared screens, with a token separate from the owner's.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from core.database import get_database
from middlewares.auth_middleware import require_owner
from services import staff as svc
from services.staff import SHIFT_HOURS, StaffError

# Owner: staff and table setup, under the owner's tenant.
owner_staff_routes = APIRouter(prefix="/tenant/current", tags=["Staff"])

# Staff: the iPad and the shared screens.
staff_routes = APIRouter(prefix="/staff", tags=["Staff"])

STAFF_COOKIE = "staff_token"


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
    return {"staff": await svc.list_staff(db, _owner_tenant(current_user))}


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


@owner_staff_routes.put("/dine-tables/count")
async def owner_set_tables(payload: TableCountBody, db=Depends(get_database), current_user: dict = Depends(require_owner)):
    try:
        return {"count": await svc.set_table_count(db, _owner_tenant(current_user), payload.count)}
    except StaffError as e:
        raise _fail(e)


# ---------------------------------------------------------------------------
# Staff sign-in
# ---------------------------------------------------------------------------
class SignInBody(BaseModel):
    restaurant: str = Field(min_length=1, max_length=80)
    staff_id: str
    pin: str = Field(min_length=4, max_length=4)
    device: Optional[str] = Field(default="iPad", max_length=40)


@staff_routes.get("/roster")
async def staff_roster(restaurant: str, db=Depends(get_database)):
    """Waiter names for the sign-in list. No PINs."""
    tenant_id = await _tenant_id_for(db, restaurant)
    return {"waiters": await svc.roster(db, tenant_id)}


@staff_routes.post("/sign-in")
async def staff_sign_in(payload: SignInBody, response: Response, db=Depends(get_database)):
    tenant_id = await _tenant_id_for(db, payload.restaurant)
    try:
        result = await svc.sign_in(db, tenant_id, payload.staff_id, payload.pin, payload.device or "iPad")
    except StaffError as e:
        raise _fail(e)
    response.set_cookie(
        STAFF_COOKIE, result["token"], max_age=SHIFT_HOURS * 3600,
        httponly=True, secure=True, samesite="lax", path="/",
    )
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
