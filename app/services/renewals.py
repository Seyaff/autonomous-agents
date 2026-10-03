"""
The daily billing job: renewals, overdue invoices and cancellations (PRICING.md section 4).

- A period that ends creates the next invoice (plan fee plus extra chats from the closing
  period), due in 7 days. A scheduled downgrade takes effect here.
- An open renewal invoice past its due date makes the subscription past_due.
  Seven days after the due date it becomes paused.
- A canceled subscription stops at its period end, with no new invoice.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from services.billing import EXTRA_CHAT_PKR, PLANS, add_months, chats_used
from services.invoices import DUE_DAYS, INVOICES, next_invoice_id, plan_fee_pkr

logger = logging.getLogger(__name__)

PAUSE_AFTER_DUE_DAYS = 7


def _utc(dt: datetime) -> datetime:
    """Mongo returns naive datetimes. They are always UTC here."""
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


async def _create_renewal(db, tenant: Dict[str, Any], now: datetime) -> None:
    sub = tenant["subscription"]
    tenant_id = tenant["tenant_id"]
    closing_plan = sub.get("plan", "basic")
    interval = sub.get("interval", "month")
    next_plan = sub.get("pending_plan") or closing_plan

    # Extra chats: whatever went over the closing plan's included chats.
    used = await chats_used(db, tenant_id, sub.get("current_period_start") or now)
    extra_chats = max(0, used - PLANS[closing_plan]["ai_conversations_per_month"])
    extra_pkr = extra_chats * EXTRA_CHAT_PKR

    fee = plan_fee_pkr(next_plan, interval)
    period_start = sub["current_period_end"]
    period_end = add_months(period_start, 12 if interval == "year" else 1)

    lines = [{
        "description": f"{PLANS[next_plan]['name']} plan ({'yearly' if interval == 'year' else 'monthly'})",
        "quantity": 1,
        "amount_pkr": fee,
    }]
    if extra_pkr:
        lines.append({
            "description": f"Extra AI chats ({extra_chats} × Rs {EXTRA_CHAT_PKR})",
            "quantity": extra_chats,
            "amount_pkr": extra_pkr,
        })

    invoice = {
        "invoice_id": await next_invoice_id(db, now),
        "tenant_id": tenant_id,
        "purpose": "renewal",
        "plan_key": next_plan,
        "interval": interval,
        "period_start": period_start,
        "period_end": period_end,
        "lines": lines,
        "amount_pkr": fee + extra_pkr,
        "extra_chat_pkr": EXTRA_CHAT_PKR,
        "status": "open",
        "due_at": now + timedelta(days=DUE_DAYS),
        "paid_at": None,
        "provider": None,
        "payment_reference": None,
        "created_at": now,
        "updated_at": now,
    }
    await db[INVOICES].insert_one(invoice)

    await db["tenants"].update_one({"tenant_id": tenant_id}, {"$set": {
        "subscription.plan": next_plan,
        "subscription.pending_plan": None,
        "subscription.current_period_start": period_start,
        "subscription.current_period_end": period_end,
        "updated_at": now,
    }})
    logger.info(f"[billing] renewal {invoice['invoice_id']} for {tenant_id}: Rs {fee + extra_pkr}")


async def run_billing_jobs(db, now: datetime | None = None) -> Dict[str, int]:
    """One pass over every subscription. Safe to run more than once a day."""
    now = now or datetime.now(timezone.utc)
    counts = {"renewed": 0, "canceled": 0, "past_due": 0, "paused": 0}

    # 1. Periods that have ended.
    ending = db["tenants"].find({
        "subscription.status": {"$in": ["active", "past_due", "paused"]},
        "subscription.current_period_end": {"$lte": now},
    })
    async for tenant in ending:
        sub = tenant["subscription"]
        if sub.get("cancel_at_period_end"):
            await db["tenants"].update_one({"tenant_id": tenant["tenant_id"]}, {"$set": {
                "subscription.status": "canceled", "updated_at": now,
            }})
            counts["canceled"] += 1
            continue
        # One renewal invoice at a time. Wait for it to be paid first.
        if await db[INVOICES].find_one({"tenant_id": tenant["tenant_id"], "purpose": "renewal", "status": "open"}):
            continue
        await _create_renewal(db, tenant, now)
        counts["renewed"] += 1

    # 2. Unpaid renewal invoices: past due after the due date, paused a week later.
    overdue = db[INVOICES].find({"purpose": "renewal", "status": "open", "due_at": {"$lt": now}})
    async for invoice in overdue:
        tenant_id = invoice["tenant_id"]
        paused_at = _utc(invoice["due_at"]) + timedelta(days=PAUSE_AFTER_DUE_DAYS)
        if now >= paused_at:
            await db["tenants"].update_one({"tenant_id": tenant_id, "subscription.status": {"$ne": "canceled"}},
                                           {"$set": {"subscription.status": "paused", "updated_at": now}})
            counts["paused"] += 1
        else:
            await db["tenants"].update_one({"tenant_id": tenant_id, "subscription.status": "active"},
                                           {"$set": {"subscription.status": "past_due", "updated_at": now}})
            counts["past_due"] += 1

    logger.info(f"[billing] daily job: {counts}")
    return counts
