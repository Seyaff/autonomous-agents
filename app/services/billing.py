"""
Plan limits and AI usage metering.

Usage is counted per tenant per calendar month (UTC). An AI conversation is
counted once per month, the first time the agent replies in it, so a busy
chat doesn't use up the quota faster than it should.

Plans, prices and the trial follow PRICING.md (locked). Change prices there first.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from pymongo.errors import DuplicateKeyError

logger = logging.getLogger(__name__)

DEFAULT_PLAN = "basic"
EXTRA_CHAT_PKR = 3
TRIAL_DAYS = 14
TRIAL_CHAT_CAP = 100

# PRICING.md section 1. Prices in PKR, whole rupees.
PLANS: Dict[str, Dict[str, Any]] = {
    "basic": {
        "name": "Basic",
        "price_monthly_pkr": 2999,
        "price_yearly_pkr": 29990,
        "ai_conversations_per_month": 200,
    },
    "standard": {
        "name": "Standard",
        "price_monthly_pkr": 5999,
        "price_yearly_pkr": 59990,
        "ai_conversations_per_month": 600,
    },
    "pro": {
        "name": "Pro",
        "price_monthly_pkr": 11999,
        "price_yearly_pkr": 119990,
        "ai_conversations_per_month": 1500,
    },
}

# Plan names that existing tenants used before the new plans.
LEGACY_PLAN_MAP = {"starter": "basic", "growth": "standard", "scale": "pro"}

USAGE = "usage_counters"
USAGE_CONVERSATIONS = "usage_conversations"


def add_months(dt: datetime, months: int) -> datetime:
    """Same day next month(s), or the last day of the month when it's shorter."""
    import calendar

    month_index = dt.month - 1 + months
    year = dt.year + month_index // 12
    month = month_index % 12 + 1
    day = min(dt.day, calendar.monthrange(year, month)[1])
    return dt.replace(year=year, month=month, day=day)


def current_period(now: Optional[datetime] = None) -> str:
    now = now or datetime.now(timezone.utc)
    return now.strftime("%Y-%m")


def new_subscription(now: Optional[datetime] = None) -> Dict[str, Any]:
    """A new restaurant starts on a 14-day trial. No payment needed."""
    now = now or datetime.now(timezone.utc)
    return {
        "plan": DEFAULT_PLAN,
        "interval": "month",
        "status": "trialing",
        "trial_ends_at": now + timedelta(days=TRIAL_DAYS),
        "current_period_start": None,
        "current_period_end": None,
        "cancel_at_period_end": False,
    }


def subscription_for(tenant: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """The tenant's subscription. Tenants from before billing fall back to their old plan name."""
    tenant = tenant or {}
    sub = tenant.get("subscription")
    if sub:
        return sub
    legacy = tenant.get("plan")
    plan_key = LEGACY_PLAN_MAP.get(legacy, legacy) if legacy else "standard"
    return {"plan": plan_key if plan_key in PLANS else DEFAULT_PLAN, "status": "trialing", "interval": "month"}


def plan_for(tenant: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    key = subscription_for(tenant).get("plan") or DEFAULT_PLAN
    if key not in PLANS:
        key = DEFAULT_PLAN
    return {"key": key, **PLANS[key]}


def allowance_for(tenant: Optional[Dict[str, Any]]) -> int:
    """AI chats this tenant may use this month: the trial cap while trialing, else the plan."""
    if subscription_for(tenant).get("status") == "trialing":
        return TRIAL_CHAT_CAP
    return plan_for(tenant)["ai_conversations_per_month"]


async def agent_allowed(db, tenant: Dict[str, Any], now: Optional[datetime] = None) -> Tuple[bool, str]:
    """Whether the agent may reply to customers for this tenant right now.

    Paused and canceled stop the agent. A trial stops it when it has ended or
    reached its chat cap. Other statuses keep working.
    """
    now = now or datetime.now(timezone.utc)
    sub = subscription_for(tenant)
    status = sub.get("status")
    if status in ("paused", "canceled"):
        return False, f"subscription {status}"
    if status == "trialing":
        ends = sub.get("trial_ends_at")
        if ends and ends.tzinfo is None:
            ends = ends.replace(tzinfo=timezone.utc)
        if ends and now >= ends:
            return False, "trial ended"
        used = await chats_used(db, tenant["tenant_id"], now)
        if used >= TRIAL_CHAT_CAP:
            return False, "trial chat cap reached"
    return True, "ok"


async def chats_used(db, tenant_id: str, now: Optional[datetime] = None) -> int:
    counter = await db[USAGE].find_one({"tenant_id": tenant_id, "period": current_period(now)}) or {}
    return int(counter.get("ai_conversations", 0))


async def migrate_subscriptions(db, now: Optional[datetime] = None) -> int:
    """Gives tenants created before billing a subscription, with a 14-day trial starting now."""
    now = now or datetime.now(timezone.utc)
    migrated = 0
    query = {"subscription": {"$exists": False}}
    for tenant in await db["tenants"].find(query, {"tenant_id": 1, "plan": 1}).to_list(length=None):
        plan_key = subscription_for(tenant)["plan"]
        sub = {**new_subscription(now), "plan": plan_key}
        result = await db["tenants"].update_one(
            {"tenant_id": tenant["tenant_id"], "subscription": {"$exists": False}},
            {"$set": {"subscription": sub, "updated_at": now}},
        )
        migrated += result.modified_count
    if migrated:
        logger.info(f"[billing] gave {migrated} existing tenants a {TRIAL_DAYS}-day trial")
    return migrated



def tokens_from_messages(messages: List[Any]) -> int:
    """Sums the model's own usage reports for the messages it produced this turn."""
    total = 0
    for m in messages:
        usage = getattr(m, "usage_metadata", None) or {}
        total += int(usage.get("total_tokens") or 0)
    return total


async def record_agent_reply(db, tenant_id: str, conversation_id: str, tokens: int) -> None:
    """Counts one agent reply. Never raises: metering must not break a customer reply."""
    period = current_period()
    try:
        # Each conversation is counted once per period.
        try:
            await db[USAGE_CONVERSATIONS].insert_one({
                "tenant_id": tenant_id,
                "period": period,
                "conversation_id": conversation_id,
                "created_at": datetime.now(timezone.utc),
            })
            new_conversation = 1
        except DuplicateKeyError:
            new_conversation = 0

        await db[USAGE].update_one(
            {"tenant_id": tenant_id, "period": period},
            {
                "$inc": {
                    "ai_conversations": new_conversation,
                    "ai_messages": 1,
                    "tokens_used": tokens,
                },
                "$set": {"updated_at": datetime.now(timezone.utc)},
                "$setOnInsert": {"tenant_id": tenant_id, "period": period},
            },
            upsert=True,
        )
    except Exception as e:
        logger.warning(f"Usage metering failed for {tenant_id}: {e}")


async def ensure_billing_indexes(db) -> None:
    await db[USAGE].create_index([("tenant_id", 1), ("period", 1)], unique=True, name="uniq_usage_period")
    await db[USAGE_CONVERSATIONS].create_index(
        [("tenant_id", 1), ("period", 1), ("conversation_id", 1)],
        unique=True,
        name="uniq_usage_conversation_period",
    )


async def usage_for_tenant(db, tenant: Dict[str, Any]) -> Dict[str, Any]:
    period = current_period()
    counter = await db[USAGE].find_one({"tenant_id": tenant["tenant_id"], "period": period}) or {}
    plan = plan_for(tenant)
    return {
        "plan_key": plan["key"],
        "plan_name": plan["name"],
        "period": period,
        "used": int(counter.get("ai_conversations", 0)),
        "limit": allowance_for(tenant),
        "ai_messages": int(counter.get("ai_messages", 0)),
        "tokens_used": int(counter.get("tokens_used", 0)),
    }
