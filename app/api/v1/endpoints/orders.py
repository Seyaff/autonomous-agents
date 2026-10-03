import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from core.database import get_database
from core.events import broadcast_order_update
from middlewares.auth_middleware import require_owner
from services.order_service import (
    ORDER_STATUSES,
    is_valid_transition,
    notify_customer_status,
    parse_range_bound,
    tenant_timezone,
)

logger = logging.getLogger(__name__)

order_router = APIRouter(prefix="/orders", tags=["Orders"])


class OrderStatusUpdate(BaseModel):
    status: str = Field(..., description="One of: pending, accepted, preparing, out_for_delivery, delivered, cancelled")
    notes: Optional[str] = Field(None, description="Optional notes on status update")


@order_router.get("")
async def list_orders(
    status_filter: Optional[str] = Query(None, alias="status"),
    from_: Optional[str] = Query(None, alias="from", description="ISO datetime, inclusive. Naive values are in the tenant's timezone."),
    to: Optional[str] = Query(None, description="ISO datetime, exclusive. Naive values are in the tenant's timezone."),
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
    current_user: dict = Depends(require_owner),
    db = Depends(get_database)
):
    """Lists orders for the authenticated restaurant owner's active tenant."""
    tenant_id = current_user.get("active_tenant_id")
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active tenant linked to your account. Please complete onboarding."
        )

    query: Dict[str, Any] = {"tenant_id": tenant_id}
    if status_filter:
        query["status"] = status_filter.lower()

    if from_ or to:
        tenant = await db["tenants"].find_one({"tenant_id": tenant_id})
        tz_name = tenant_timezone(tenant)
        window: Dict[str, Any] = {}
        try:
            if from_:
                window["$gte"] = parse_range_bound(from_, tz_name)
            if to:
                window["$lt"] = parse_range_bound(to, tz_name)
        except ValueError:
            raise HTTPException(status_code=400, detail="from/to must be ISO datetimes, e.g. 2026-10-03T00:00:00")
        query["created_at"] = window

    # ✅ PyMongo async: find() returns a cursor directly (no await needed here)
    cursor = db["orders"].find(query).sort("created_at", -1).skip(skip).limit(limit)
    orders = await cursor.to_list(length=limit)

    for o in orders:
        if "_id" in o:
            o["_id"] = str(o["_id"])

    total = await db["orders"].count_documents(query)

    return {
        "status": "success",
        "total": total,
        "orders": orders
    }


@order_router.get("/stats/summary")
async def get_orders_summary(
    current_user: dict = Depends(require_owner),
    db = Depends(get_database)
):
    """Calculates order counts, revenue, and active tickets for dashboard metric cards."""
    tenant_id = current_user.get("active_tenant_id")
    if not tenant_id:
        return {
            "total_orders": 0,
            "total_revenue": 0.0,
            "pending_orders": 0,
            "completed_orders": 0,
            "cancelled_orders": 0,
        }

    pipeline = [
        {"$match": {"tenant_id": tenant_id}},
        {
            "$group": {
                "_id": "$status",
                "count": {"$sum": 1},
                "revenue": {"$sum": "$total_amount"}
            }
        }
    ]

    # ✅ FIX: aggregate() returns a coroutine in PyMongo async — await it FIRST,
    # then call .to_list() on the resulting cursor.
    cursor = await db["orders"].aggregate(pipeline)
    results = await cursor.to_list(length=20)

    total_orders = 0
    total_revenue = 0.0
    pending_count = 0
    completed_count = 0
    cancelled_count = 0

    for r in results:
        st = r["_id"]
        c = r["count"]
        rev = r.get("revenue") or 0.0  # ✅ guard: $sum returns None if no docs match
        total_orders += c
        # Revenue counts confirmed-onward orders only — a "pending" order
        # hasn't even been accepted by the restaurant yet, so it isn't
        # real revenue any more than a cancelled one is.
        if st not in ["cancelled", "pending"]:
            total_revenue += rev
        if st in ["pending", "accepted", "preparing"]:
            pending_count += c
        elif st == "delivered":
            completed_count += c
        elif st == "cancelled":
            cancelled_count += c

    return {
        "total_orders": total_orders,
        "total_revenue": round(total_revenue, 2),
        "pending_orders": pending_count,
        "completed_orders": completed_count,
        "cancelled_orders": cancelled_count,
    }


@order_router.get("/{order_id}")
async def get_order_by_id(
    order_id: str,
    current_user: dict = Depends(require_owner),
    db = Depends(get_database)
):
    """Retrieves single order details."""
    tenant_id = current_user.get("active_tenant_id")
    # ✅ FIX: guard against missing tenant_id (prevents cross-tenant leak
    # where tenant_id=None could match docs missing the field)
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active tenant linked to your account. Please complete onboarding."
        )

    order = await db["orders"].find_one({"order_id": order_id, "tenant_id": tenant_id})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if "_id" in order:
        order["_id"] = str(order["_id"])
    return order


@order_router.patch("/{order_id}")
async def update_order_status(
    order_id: str,
    payload: OrderStatusUpdate,
    current_user: dict = Depends(require_owner),
    db = Depends(get_database)
):
    """Moves an order to a new status. Only the transitions in ORDER_TRANSITIONS
    are allowed (409 otherwise). The change is appended to status_history, the
    customer is told when Meta allows it, and the result says whether they were."""
    tenant_id = current_user.get("active_tenant_id")
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active tenant linked to your account. Please complete onboarding."
        )

    order = await db["orders"].find_one({"order_id": order_id, "tenant_id": tenant_id})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    new_status = payload.status.lower()
    if new_status not in ORDER_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {list(ORDER_STATUSES)}")

    current_status = order.get("status", "pending")
    if not is_valid_transition(current_status, new_status):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot move order from '{current_status}' to '{new_status}'.",
        )

    now = datetime.now(timezone.utc)
    tenant = await db["tenants"].find_one({"tenant_id": tenant_id})
    customer_notified = await notify_customer_status(
        db, tenant or {"tenant_id": tenant_id}, order, new_status
    )

    history_entry = {
        "status": new_status,
        "at": now,
        "by": "owner",
        "by_user_id": current_user.get("user_id"),
        "customer_notified": customer_notified,
    }
    update_doc: Dict[str, Any] = {"status": new_status, "updated_at": now}
    if payload.notes:
        update_doc["admin_notes"] = payload.notes

    await db["orders"].update_one(
        {"order_id": order_id, "tenant_id": tenant_id},
        {"$set": update_doc, "$push": {"status_history": history_entry}},
    )

    order.update(update_doc)
    order.setdefault("status_history", []).append(history_entry)
    order.pop("_id", None)

    await broadcast_order_update(
        tenant_id=tenant_id,
        event_type="order.updated",
        order_data=order
    )

    return {
        "status": "success",
        "message": f"Order {order_id} marked as {new_status}",
        "order": order,
        "customer_notified": customer_notified,
    }
