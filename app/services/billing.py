"""
Plan limits and AI usage metering.

Usage is counted per tenant per calendar month (UTC). An AI conversation is
counted once per month, the first time the agent replies in it, so a busy
chat doesn't use up the quota faster than it should.

The plan limits below are placeholders until pricing is decided. They are
config, not code paths, so changing them is a one-line edit.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pymongo.errors import DuplicateKeyError

logger = logging.getLogger(__name__)

DEFAULT_PLAN = "growth"

# Placeholder limits. AI conversations per month.
PLANS: Dict[str, Dict[str, Any]] = {
    "starter": {"name": "Starter", "ai_conversations_per_month": 500},
    "growth": {"name": "Growth", "ai_conversations_per_month": 2000},
    "scale": {"name": "Scale", "ai_conversations_per_month": 10000},
}

USAGE = "usage_counters"
USAGE_CONVERSATIONS = "usage_conversations"


def current_period(now: Optional[datetime] = None) -> str:
    now = now or datetime.now(timezone.utc)
    return now.strftime("%Y-%m")


def plan_for(tenant: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    key = (tenant or {}).get("plan") or DEFAULT_PLAN
    plan = PLANS.get(key, PLANS[DEFAULT_PLAN])
    return {"key": key if key in PLANS else DEFAULT_PLAN, **plan}


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
        "limit": plan["ai_conversations_per_month"],
        "ai_messages": int(counter.get("ai_messages", 0)),
        "tokens_used": int(counter.get("tokens_used", 0)),
    }
