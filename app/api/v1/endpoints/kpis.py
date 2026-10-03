import statistics
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Literal, Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from core.database import get_database
from middlewares.auth_middleware import require_owner
from services.order_service import REVENUE_EXCLUDED_STATUSES, tenant_timezone

kpi_router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

REPLY_SENDERS = ("agent", "human")


class KpiResponse(BaseModel):
    range: Literal["today", "7d"]
    currency: str
    orders: int
    revenue: float
    conversations: int
    ai_handled_pct: float
    median_first_reply_s: Optional[float]
    needs_you: int


def _range_start(range_name: str, tz_name: str) -> datetime:
    now_local = datetime.now(ZoneInfo(tz_name))
    if range_name == "today":
        start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        start_local = now_local - timedelta(days=7)
    return start_local.astimezone(timezone.utc)


async def _median_first_reply_seconds(db, tenant_id: str, since: datetime) -> Optional[float]:
    """Median seconds from a customer's first message to the first reply after it,
    across conversations that started since `since`."""
    cursor = db["messages"].find(
        {
            "tenant_id": tenant_id,
            "created_at": {"$gte": since},
            "sender": {"$in": ["customer", *REPLY_SENDERS]},
        },
        {"conversation_id": 1, "sender": 1, "created_at": 1},
    ).sort("created_at", 1)

    first_customer: Dict[str, datetime] = {}
    gaps: List[float] = []
    async for m in cursor:
        conv = m["conversation_id"]
        at = m["created_at"]
        at = at if at.tzinfo else at.replace(tzinfo=timezone.utc)
        if m["sender"] == "customer":
            first_customer.setdefault(conv, at)
        elif conv in first_customer:
            gaps.append((at - first_customer.pop(conv)).total_seconds())

    if not gaps:
        return None
    return round(statistics.median(gaps), 1)


@kpi_router.get("/kpis", response_model=KpiResponse)
async def get_kpis(
    range_name: Literal["today", "7d"] = Query("today", alias="range"),
    current_user: dict = Depends(require_owner),
    db=Depends(get_database),
):
    """Headline numbers for the dashboard strip. Revenue excludes pending and
    cancelled orders, the same rule as the orders summary."""
    tenant_id = current_user.get("active_tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="No active tenant linked to your account.")

    tenant = await db["tenants"].find_one({"tenant_id": tenant_id}) or {}
    since = _range_start(range_name, tenant_timezone(tenant))

    orders = await db["orders"].count_documents({"tenant_id": tenant_id, "created_at": {"$gte": since}})

    revenue_cursor = await db["orders"].aggregate([
        {"$match": {
            "tenant_id": tenant_id,
            "created_at": {"$gte": since},
            "status": {"$nin": list(REVENUE_EXCLUDED_STATUSES)},
        }},
        {"$group": {"_id": None, "total": {"$sum": "$total_amount"}}},
    ])
    revenue_rows = await revenue_cursor.to_list(length=1)
    revenue = round(revenue_rows[0]["total"], 2) if revenue_rows else 0.0

    active_conversations = {"tenant_id": tenant_id, "last_activity_at": {"$gte": since}}
    conversations = await db["conversations"].count_documents(active_conversations)
    ai_only = await db["conversations"].count_documents({**active_conversations, "handed_over_at": None})
    ai_handled_pct = round(100.0 * ai_only / conversations, 1) if conversations else 0.0

    needs_you = await db["conversations"].count_documents(
        {"tenant_id": tenant_id, "escalation.active": True}
    )

    return KpiResponse(
        range=range_name,
        currency=tenant.get("currency") or "USD",
        orders=orders,
        revenue=revenue,
        conversations=conversations,
        ai_handled_pct=ai_handled_pct,
        median_first_reply_s=await _median_first_reply_seconds(db, tenant_id, since),
        needs_you=needs_you,
    )
