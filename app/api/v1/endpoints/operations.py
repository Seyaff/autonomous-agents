"""
Operator view for the founder account: every restaurant's health and the latest
alerts across all of them. Read-only. Owners never see this.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Query

from core.database import get_database
from middlewares.auth_middleware import require_founder
from services.billing import PLANS, DEFAULT_PLAN, current_period
from services.setup_status import setup_is_complete

ops_router = APIRouter(prefix="/ops", tags=["Operations"])


def _day_start() -> datetime:
    now = datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


@ops_router.get("/restaurants")
async def restaurants(
    current_user: dict = Depends(require_founder),
    db=Depends(get_database),
):
    """One row per restaurant: is it live, is anything broken, and how busy is it."""
    tenants: List[Dict[str, Any]] = await db["tenants"].find({}, {
        "tenant_id": 1, "business_name": 1, "country": 1, "setup": 1,
        "whatsapp_status": 1, "whatsapp_last_error": 1, "whatsapp_connected": 1,
        "display_phone_number": 1, "agent_enabled": 1, "plan": 1, "created_at": 1,
    }).sort("created_at", -1).to_list(length=500)

    since_24h = datetime.now(timezone.utc) - timedelta(hours=24)
    today = _day_start()
    period = current_period()
    rows: List[Dict[str, Any]] = []

    for t in tenants:
        tid = t["tenant_id"]
        owner = await db["users"].find_one({"tenants": tid}, {"email": 1, "full_name": 1})
        last = await db["conversations"].find_one(
            {"tenant_id": tid}, {"last_activity_at": 1}, sort=[("last_activity_at", -1)]
        )
        alerts_unread = await db["owner_alerts"].count_documents({"tenant_id": tid, "read_at": None})
        alerts_critical = await db["owner_alerts"].count_documents(
            {"tenant_id": tid, "read_at": None, "severity": "critical"}
        )
        failed_24h = await db["messages"].count_documents(
            {"tenant_id": tid, "status": "failed", "created_at": {"$gte": since_24h}}
        )
        escalations = await db["conversations"].count_documents(
            {"tenant_id": tid, "escalation.active": True}
        )
        orders_today = await db["orders"].count_documents({"tenant_id": tid, "created_at": {"$gte": today}})
        messages_today = await db["messages"].count_documents({"tenant_id": tid, "created_at": {"$gte": today}})
        usage = await db["usage_counters"].find_one({"tenant_id": tid, "period": period}) or {}
        plan = PLANS.get(t.get("plan") or DEFAULT_PLAN, PLANS[DEFAULT_PLAN])

        # "shared_number": not on its own WhatsApp connection, so it sends and receives
        # through the shared .env number (the normal state in development). That is not a fault.
        if t.get("whatsapp_status") == "error":
            whatsapp = "error"
        elif t.get("whatsapp_connected") or t.get("whatsapp_status") == "connected":
            whatsapp = "connected"
        else:
            whatsapp = "shared_number"
        setup_done = setup_is_complete(t)
        if not setup_done:
            health = "setting_up"
        elif whatsapp == "error" or alerts_critical:
            health = "needs_attention"
        else:
            health = "healthy"

        rows.append({
            "tenant_id": tid,
            "business_name": t.get("business_name"),
            "country": t.get("country"),
            "owner_email": (owner or {}).get("email"),
            "owner_name": (owner or {}).get("full_name"),
            "health": health,
            "setup_complete": setup_done,
            "whatsapp_status": whatsapp,
            "whatsapp_error": t.get("whatsapp_last_error"),
            "display_phone_number": t.get("display_phone_number"),
            "agent_enabled": t.get("agent_enabled", True),
            "last_customer_activity": (last or {}).get("last_activity_at"),
            "messages_today": messages_today,
            "orders_today": orders_today,
            "failed_messages_24h": failed_24h,
            "escalations_open": escalations,
            "alerts_unread": alerts_unread,
            "alerts_critical": alerts_critical,
            "ai_conversations_this_month": int(usage.get("ai_conversations", 0)),
            "plan_limit": plan["ai_conversations_per_month"],
            "created_at": t.get("created_at"),
        })

    order = {"needs_attention": 0, "setting_up": 1, "healthy": 2}
    rows.sort(key=lambda r: (order[r["health"]], -r["alerts_critical"]))
    return {"restaurants": rows, "total": len(rows)}


@ops_router.get("/alerts")
async def alerts(
    limit: int = Query(50, ge=1, le=200),
    unread_only: bool = False,
    current_user: dict = Depends(require_founder),
    db=Depends(get_database),
):
    """The latest owner alerts across every restaurant."""
    query: Dict[str, Any] = {}
    if unread_only:
        query["read_at"] = None
    docs = await db["owner_alerts"].find(query).sort("created_at", -1).limit(limit).to_list(length=limit)
    names = {}
    out = []
    for d in docs:
        tid = d["tenant_id"]
        if tid not in names:
            t = await db["tenants"].find_one({"tenant_id": tid}, {"business_name": 1})
            names[tid] = (t or {}).get("business_name", tid)
        out.append({
            "id": str(d["_id"]),
            "tenant_id": tid,
            "business_name": names[tid],
            "kind": d.get("kind"),
            "severity": d.get("severity"),
            "title": d.get("title"),
            "detail": d.get("detail"),
            "created_at": d.get("created_at"),
            "read": d.get("read_at") is not None,
        })
    return {"alerts": out}
