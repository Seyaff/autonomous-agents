"""
Invoices: creating them, paying them through the payment provider, and turning a paid
subscription invoice into an active subscription.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

from pymongo import ReturnDocument

from services.billing import EXTRA_CHAT_PKR, PLANS, add_months
from services.payments import get_payment_provider

logger = logging.getLogger(__name__)

INVOICES = "invoices"
DUE_DAYS = 7
PUBLIC_FIELDS = {"_id": 0}


async def next_invoice_id(db, now: datetime) -> str:
    year = now.year
    doc = await db["counters"].find_one_and_update(
        {"_id": f"invoice-{year}"},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return f"INV-{year}-{int(doc['seq']):06d}"


def plan_fee_pkr(plan_key: str, interval: str) -> int:
    plan = PLANS[plan_key]
    return plan["price_yearly_pkr"] if interval == "year" else plan["price_monthly_pkr"]


async def create_subscription_invoice(db, tenant_id: str, plan_key: str, interval: str, now: Optional[datetime] = None) -> Dict[str, Any]:
    """The first invoice for a plan. The period starts when it's paid."""
    now = now or datetime.now(timezone.utc)
    period_end = add_months(now, 12 if interval == "year" else 1)
    amount = plan_fee_pkr(plan_key, interval)
    period_label = "yearly" if interval == "year" else "monthly"
    invoice = {
        "invoice_id": await next_invoice_id(db, now),
        "tenant_id": tenant_id,
        "purpose": "subscription",
        "plan_key": plan_key,
        "interval": interval,
        "period_start": now,
        "period_end": period_end,
        "lines": [{
            "description": f"{PLANS[plan_key]['name']} plan ({period_label})",
            "quantity": 1,
            "amount_pkr": amount,
        }],
        "amount_pkr": amount,
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
    return invoice


async def activate_subscription(db, tenant_id: str, invoice: Dict[str, Any], now: datetime) -> Dict[str, Any]:
    """A paid subscription invoice starts the plan for its period. The trial date is kept."""
    update = {
        "subscription.plan": invoice["plan_key"],
        "subscription.interval": invoice["interval"],
        "subscription.status": "active",
        "subscription.current_period_start": now,
        "subscription.current_period_end": add_months(now, 12 if invoice["interval"] == "year" else 1),
        "subscription.cancel_at_period_end": False,
        "updated_at": now,
    }
    await db["tenants"].update_one({"tenant_id": tenant_id}, {"$set": update})
    tenant = await db["tenants"].find_one({"tenant_id": tenant_id}, {"subscription": 1}) or {}
    return tenant.get("subscription", {})


async def pay_open_invoice(db, invoice: Dict[str, Any], method: str = "card") -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Pays an open invoice through the provider. Returns (paid invoice, None), or (None, error).
    A failed payment leaves the invoice open."""
    provider = get_payment_provider()
    result = await provider.pay_invoice(invoice, method)
    if not result.ok:
        logger.info(f"[billing] payment failed for {invoice['invoice_id']}: {result.error}")
        return None, result.error or "The payment didn't go through. Try again."

    now = datetime.now(timezone.utc)
    await db[INVOICES].update_one(
        {"invoice_id": invoice["invoice_id"], "tenant_id": invoice["tenant_id"]},
        {"$set": {
            "status": "paid",
            "paid_at": now,
            "provider": provider.name,
            "payment_reference": result.reference,
            "updated_at": now,
        }},
    )
    paid = await db[INVOICES].find_one({"invoice_id": invoice["invoice_id"]}, PUBLIC_FIELDS)

    if paid.get("purpose") == "subscription":
        await activate_subscription(db, paid["tenant_id"], paid, now)
    return paid, None
