"""
Staff for dine-in: waiters, reception and kitchen. The owner sets each person's PIN.

Rules this module enforces:
- A PIN is stored as a bcrypt hash, never as typed.
- One device per person: signing in on a new iPad ends the session on the old one.
- After three wrong PINs the person is locked until the owner unlocks them.
- Prices come from the menu, never from the device.
- Kitchen moves a ticket New -> Cooking -> Ready. The waiter marks it served, bills and collects cash.
- Every slip, ticket and bill is queued as a print job. The print agent comes later.
"""

import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import bcrypt
import jwt

from core.settings import settings
from services.availability import MENU_ITEMS, today_for

STAFF = "staff"
TABLE_ORDERS = "table_orders"
PRINT_JOBS = "print_jobs"
ROLES = ("waiter", "reception", "kitchen")
MAX_WRONG_PINS = 3
SHIFT_HOURS = 12
MAX_TABLES = 200
MAX_QTY = 50
TOKEN_TYPE = "staff"


class StaffError(Exception):
    """A message the owner or the staff member can read."""


def valid_pin(pin: Any) -> bool:
    return isinstance(pin, str) and len(pin) == 4 and pin.isdigit()


def hash_pin(pin: str) -> str:
    return bcrypt.hashpw(pin.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def pin_matches(pin: str, hashed: str) -> bool:
    return bcrypt.checkpw(pin.encode("utf-8"), hashed.encode("utf-8"))


def status_of(doc: Dict[str, Any]) -> str:
    if doc.get("removed"):
        return "Removed"
    if doc.get("locked"):
        return "Locked"
    if doc.get("session_id"):
        return f"Signed in on {doc.get('device') or 'a device'}"
    return "Signed out"


def public_staff(doc: Dict[str, Any]) -> Dict[str, Any]:
    """What the owner sees. Never the PIN or its hash."""
    return {
        "staff_id": doc["staff_id"],
        "name": doc["name"],
        "role": doc["role"],
        "status": status_of(doc),
        "locked": bool(doc.get("locked")),
        "removed": bool(doc.get("removed")),
    }


async def _get_staff(db, tenant_id: str, staff_id: str) -> Dict[str, Any]:
    doc = await db[STAFF].find_one({"tenant_id": tenant_id, "staff_id": staff_id})
    if not doc or doc.get("removed"):
        raise StaffError("That person isn't on the staff list.")
    return doc


# ---------------------------------------------------------------------------
# Owner: staff management
# ---------------------------------------------------------------------------
async def create_staff(db, tenant_id: str, name: str, role: str, pin: str) -> Dict[str, Any]:
    name = (name or "").strip()
    if not name or len(name) > 40:
        raise StaffError("Enter the person's name (up to 40 characters).")
    if role not in ROLES:
        raise StaffError("Choose waiter, reception or kitchen.")
    if not valid_pin(pin):
        raise StaffError("The PIN must be 4 digits.")
    doc = {
        "staff_id": f"stf_{uuid.uuid4().hex[:12]}",
        "tenant_id": tenant_id,
        "name": name,
        "role": role,
        "pin_hash": hash_pin(pin),
        "wrong_pins": 0,
        "locked": False,
        "session_id": None,
        "device": None,
        "removed": False,
        "created_at": datetime.now(timezone.utc),
    }
    await db[STAFF].insert_one(doc)
    return public_staff(doc)


async def list_staff(db, tenant_id: str) -> List[Dict[str, Any]]:
    rows = await db[STAFF].find({"tenant_id": tenant_id, "removed": {"$ne": True}}).to_list(length=500)
    return [public_staff(r) for r in rows]


async def reset_pin(db, tenant_id: str, staff_id: str, pin: str) -> Dict[str, Any]:
    if not valid_pin(pin):
        raise StaffError("The PIN must be 4 digits.")
    await _get_staff(db, tenant_id, staff_id)
    # Changing the PIN also signs out any device that person was using.
    await db[STAFF].update_one(
        {"tenant_id": tenant_id, "staff_id": staff_id},
        {"$set": {"pin_hash": hash_pin(pin), "wrong_pins": 0, "locked": False, "session_id": None, "device": None}},
    )
    return public_staff(await _get_staff(db, tenant_id, staff_id))


async def unlock(db, tenant_id: str, staff_id: str) -> Dict[str, Any]:
    await _get_staff(db, tenant_id, staff_id)
    await db[STAFF].update_one({"tenant_id": tenant_id, "staff_id": staff_id}, {"$set": {"locked": False, "wrong_pins": 0}})
    return public_staff(await _get_staff(db, tenant_id, staff_id))


async def remove(db, tenant_id: str, staff_id: str) -> None:
    await _get_staff(db, tenant_id, staff_id)
    await db[STAFF].update_one(
        {"tenant_id": tenant_id, "staff_id": staff_id},
        {"$set": {"removed": True, "session_id": None, "device": None}},
    )


async def set_table_count(db, tenant_id: str, count: int) -> int:
    if not isinstance(count, int) or not 1 <= count <= MAX_TABLES:
        raise StaffError(f"Choose between 1 and {MAX_TABLES} tables.")
    await db.tenants.update_one({"tenant_id": tenant_id}, {"$set": {"dine_table_count": count}})
    return count


# ---------------------------------------------------------------------------
# Staff: sign-in and sessions
# ---------------------------------------------------------------------------
async def roster(db, tenant_id: str) -> List[Dict[str, Any]]:
    """Names the iPad shows on the sign-in screen. Waiters only, no PINs."""
    rows = await db[STAFF].find(
        {"tenant_id": tenant_id, "role": "waiter", "removed": {"$ne": True}, "locked": {"$ne": True}},
        {"_id": 0, "staff_id": 1, "name": 1},
    ).to_list(length=200)
    return [{"staff_id": r["staff_id"], "name": r["name"]} for r in rows]


def _make_token(tenant_id: str, staff_id: str, session_id: str) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": staff_id,
            "tid": tenant_id,
            "sid": session_id,
            "type": TOKEN_TYPE,
            "iat": now,
            "exp": now + timedelta(hours=SHIFT_HOURS),
            "iss": "Siyaf",
        },
        key=settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


async def sign_in(db, tenant_id: str, staff_id: str, pin: str, device: str) -> Dict[str, Any]:
    staff = await _get_staff(db, tenant_id, staff_id)
    if staff.get("role") != "waiter":
        raise StaffError("Only waiters sign in on the iPad.")
    if staff.get("locked"):
        raise StaffError("This PIN is locked. Ask the owner to unlock it.")
    if not pin_matches(pin or "", staff["pin_hash"]):
        wrong = int(staff.get("wrong_pins", 0)) + 1
        locked = wrong >= MAX_WRONG_PINS
        await db[STAFF].update_one(
            {"tenant_id": tenant_id, "staff_id": staff_id},
            {"$set": {"wrong_pins": wrong, "locked": locked}},
        )
        if locked:
            raise StaffError("Locked after 3 wrong PINs. Ask the owner to unlock it.")
        raise StaffError(f"Wrong PIN. {MAX_WRONG_PINS - wrong} tries left.")

    session_id = uuid.uuid4().hex
    await db[STAFF].update_one(
        {"tenant_id": tenant_id, "staff_id": staff_id},
        {"$set": {"wrong_pins": 0, "session_id": session_id, "device": (device or "iPad")[:40]}},
    )
    return {"token": _make_token(tenant_id, staff_id, session_id), "staff": public_staff(await _get_staff(db, tenant_id, staff_id))}


async def staff_from_token(db, token: str) -> Dict[str, Any]:
    """The staff member a token belongs to. Raises StaffError when the session has ended."""
    try:
        claims = jwt.decode(token, key=settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except jwt.PyJWTError:
        raise StaffError("Signed out. Sign in again.")
    if claims.get("type") != TOKEN_TYPE:
        raise StaffError("Signed out. Sign in again.")
    staff = await db[STAFF].find_one({"tenant_id": claims.get("tid"), "staff_id": claims.get("sub")})
    if not staff or staff.get("removed") or staff.get("locked"):
        raise StaffError("Signed out. Sign in again.")
    if staff.get("session_id") != claims.get("sid"):
        raise StaffError("Signed in on another iPad.")
    return staff


async def sign_out(db, tenant_id: str, staff_id: str) -> None:
    await db[STAFF].update_one({"tenant_id": tenant_id, "staff_id": staff_id}, {"$set": {"session_id": None, "device": None}})


# ---------------------------------------------------------------------------
# Tables and orders
# ---------------------------------------------------------------------------
def _require_role(staff: Dict[str, Any], *roles: str) -> None:
    if staff.get("role") not in roles:
        raise StaffError("Your role can't do that.")


def _order_total(order: Dict[str, Any]) -> float:
    return sum(float(i["price"]) * int(i["qty"]) for i in order["items"])


def _table_status(orders: List[Dict[str, Any]]) -> str:
    if not orders:
        return "free"
    if any(o["status"] == "billed" for o in orders):
        return "bill"
    if all(o["status"] == "served" for o in orders):
        return "served"
    if any(o["kitchen_status"] == "ready" for o in orders):
        return "ready"
    return "sent"


async def table_board(db, tenant_id: str) -> List[Dict[str, Any]]:
    tenant = await db.tenants.find_one({"tenant_id": tenant_id}) or {}
    count = int(tenant.get("dine_table_count") or 0)
    open_orders = await db[TABLE_ORDERS].find(
        {"tenant_id": tenant_id, "status": {"$in": ["sent", "served", "billed"]}}, {"_id": 0}
    ).to_list(length=1000)
    board = []
    for no in range(1, count + 1):
        mine = [o for o in open_orders if o["table_no"] == no]
        board.append({
            "table_no": no,
            "status": _table_status(mine),
            "total": sum(_order_total(o) for o in mine),
            "order_ids": [o["order_id"] for o in mine],
        })
    return board


def _slip_lines(order: Dict[str, Any], kind: str) -> List[str]:
    if kind == "kitchen_ticket":
        head = [f"KITCHEN  Table {order['table_no']}  #{order['order_id']}"]
        body = [f"{i['qty']} x {i['name']}" for i in order["items"]]
        return head + ["-" * 32] + body
    head = [f"ORDER SLIP  Table {order['table_no']}  Waiter {order['waiter_name']}"]
    body = [f"{i['qty']} x {i['name']}  {float(i['price']) * i['qty']:,.0f}" for i in order["items"]]
    return head + ["-" * 32] + body + ["-" * 32, f"TOTAL  {_order_total(order):,.0f}"]


async def _queue_print(db, tenant_id: str, kind: str, ref: str, lines: List[str]) -> None:
    await db[PRINT_JOBS].insert_one({
        "job_id": f"job_{uuid.uuid4().hex[:12]}",
        "tenant_id": tenant_id,
        "kind": kind,
        "ref": ref,
        "lines": lines,
        "status": "queued",
        "created_at": datetime.now(timezone.utc),
    })


async def send_order(db, tenant_id: str, staff: Dict[str, Any], table_no: int, lines: List[Dict[str, Any]]) -> Dict[str, Any]:
    _require_role(staff, "waiter")
    tenant = await db.tenants.find_one({"tenant_id": tenant_id}) or {}
    if not isinstance(table_no, int) or not 1 <= table_no <= int(tenant.get("dine_table_count") or 0):
        raise StaffError("That table isn't set up.")
    if not lines:
        raise StaffError("Add at least one item.")

    today = today_for(tenant)
    items = []
    for line in lines:
        name = (line.get("name") or "").strip()
        qty = line.get("qty")
        if not isinstance(qty, int) or not 1 <= qty <= MAX_QTY:
            raise StaffError(f"Quantity must be between 1 and {MAX_QTY}.")
        row = await db[MENU_ITEMS].find_one(
            {"tenant_id": tenant_id, "name": {"$regex": f"^{re.escape(name)}$", "$options": "i"}, "hidden": {"$ne": True}},
            {"_id": 0, "name": 1, "price": 1, "sold_out_on": 1},
        )
        if not row:
            raise StaffError(f"{name or 'That item'} isn't on the menu.")
        if row.get("sold_out_on") == today:
            raise StaffError(f"{row['name']} is sold out today.")
        items.append({"name": row["name"], "qty": qty, "price": float(row.get("price") or 0)})

    now = datetime.now(timezone.utc)
    order = {
        "order_id": f"TO-{uuid.uuid4().hex[:10].upper()}",
        "tenant_id": tenant_id,
        "table_no": table_no,
        "waiter_id": staff["staff_id"],
        "waiter_name": staff["name"],
        "items": items,
        "status": "sent",
        "kitchen_status": "new",
        "created_at": now,
        "updated_at": now,
    }
    await db[TABLE_ORDERS].insert_one(order)
    await _queue_print(db, tenant_id, "reception_slip", order["order_id"], _slip_lines(order, "reception_slip"))
    await _queue_print(db, tenant_id, "kitchen_ticket", order["order_id"], _slip_lines(order, "kitchen_ticket"))
    return {k: v for k, v in order.items() if k != "_id"}


async def kitchen_update(db, tenant_id: str, staff: Dict[str, Any], order_id: str, to: str) -> Dict[str, Any]:
    _require_role(staff, "kitchen")
    if to not in ("cooking", "ready"):
        raise StaffError("Choose cooking or ready.")
    order = await db[TABLE_ORDERS].find_one({"tenant_id": tenant_id, "order_id": order_id})
    if not order:
        raise StaffError("That order isn't open.")
    needed = "new" if to == "cooking" else "cooking"
    if order["kitchen_status"] != needed:
        raise StaffError("This ticket is already past that step.")
    await db[TABLE_ORDERS].update_one(
        {"tenant_id": tenant_id, "order_id": order_id},
        {"$set": {"kitchen_status": to, "updated_at": datetime.now(timezone.utc)}},
    )
    return {"order_id": order_id, "kitchen_status": to}


async def mark_served(db, tenant_id: str, staff: Dict[str, Any], order_id: str) -> Dict[str, Any]:
    _require_role(staff, "waiter")
    result = await db[TABLE_ORDERS].update_one(
        {"tenant_id": tenant_id, "order_id": order_id, "status": "sent"},
        {"$set": {"status": "served", "updated_at": datetime.now(timezone.utc)}},
    )
    if result.matched_count == 0:
        raise StaffError("That order isn't waiting to be served.")
    return {"order_id": order_id, "status": "served"}


async def request_bill(db, tenant_id: str, staff: Dict[str, Any], table_no: int) -> Dict[str, Any]:
    _require_role(staff, "waiter")
    orders = await db[TABLE_ORDERS].find(
        {"tenant_id": tenant_id, "table_no": table_no, "status": {"$in": ["sent", "served"]}}, {"_id": 0}
    ).to_list(length=200)
    if not orders:
        raise StaffError("Nothing to bill on that table.")
    now = datetime.now(timezone.utc)
    await db[TABLE_ORDERS].update_many(
        {"tenant_id": tenant_id, "order_id": {"$in": [o["order_id"] for o in orders]}},
        {"$set": {"status": "billed", "updated_at": now}},
    )
    totals: Dict[str, Dict[str, Any]] = {}
    for o in orders:
        for i in o["items"]:
            row = totals.setdefault(i["name"], {"name": i["name"], "qty": 0, "price": i["price"]})
            row["qty"] += i["qty"]
    grand = sum(float(r["price"]) * r["qty"] for r in totals.values())
    lines = [f"BILL  Table {table_no}", "-" * 32]
    lines += [f"{r['qty']} x {r['name']}  {float(r['price']) * r['qty']:,.0f}" for r in totals.values()]
    lines += ["-" * 32, f"TOTAL  {grand:,.0f}", "Cash"]
    ref = f"table-{table_no}-{now.strftime('%H%M%S')}"
    await _queue_print(db, tenant_id, "bill", ref, lines)
    return {"table_no": table_no, "total": grand, "order_ids": [o["order_id"] for o in orders]}


async def mark_paid_cash(db, tenant_id: str, staff: Dict[str, Any], table_no: int) -> Dict[str, Any]:
    _require_role(staff, "waiter")
    now = datetime.now(timezone.utc)
    result = await db[TABLE_ORDERS].update_many(
        {"tenant_id": tenant_id, "table_no": table_no, "status": "billed"},
        {"$set": {"status": "paid", "payment": {"method": "cash", "by": staff["staff_id"], "at": now}, "updated_at": now}},
    )
    if result.matched_count == 0:
        raise StaffError("Print the bill before marking it paid.")
    return {"table_no": table_no, "status": "paid", "method": "cash"}


async def open_orders(db, tenant_id: str) -> List[Dict[str, Any]]:
    rows = await db[TABLE_ORDERS].find(
        {"tenant_id": tenant_id, "status": {"$in": ["sent", "served", "billed"]}}, {"_id": 0}
    ).sort([("created_at", 1)]).to_list(length=300)
    return rows
