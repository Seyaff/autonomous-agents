from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from core.database import get_database
from middlewares.auth_middleware import require_owner
import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from services.invoices import (
    create_subscription_invoice,
    create_upgrade_invoice,
    pay_open_invoice,
    plan_fee_pkr,
    INVOICES,
    PUBLIC_FIELDS,
)
from services.billing import (
    DEFAULT_PLAN,
    EXTRA_CHAT_PKR,
    PLANS,
    TRIAL_CHAT_CAP,
    TRIAL_DAYS,
    subscription_for,
    usage_for_tenant,
)

billing_router = APIRouter(prefix="/billing", tags=["Billing"])


class UsageResponse(BaseModel):
    plan_key: str
    plan_name: str
    period: str
    used: int
    limit: int
    ai_messages: int
    tokens_used: int


@billing_router.get("/usage", response_model=UsageResponse)
async def get_usage(
    current_user: dict = Depends(require_owner),
    db=Depends(get_database),
):
    """AI usage for the active restaurant in the current month, against its plan."""
    tenant_id = current_user.get("active_tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="No active tenant linked to your account.")
    tenant = await db["tenants"].find_one({"tenant_id": tenant_id}) or {"tenant_id": tenant_id}
    return UsageResponse(**await usage_for_tenant(db, tenant))


class SubscriptionResponse(BaseModel):
    plan: str
    plan_name: str
    interval: str
    status: str
    trial_ends_at: Optional[datetime] = None
    trial_days_left: Optional[int] = None
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    cancel_at_period_end: bool
    pending_plan: Optional[str] = None
    pending_plan_name: Optional[str] = None
    next_invoice_date: Optional[datetime] = None
    next_invoice_pkr: int = 0
    meta_fee_pkr: int = 0
    price_pkr: int
    included_chats: int
    extra_chat_pkr: int
    usage: Dict[str, Any]


@billing_router.get("/subscription", response_model=SubscriptionResponse)
async def get_subscription(
    current_user: dict = Depends(require_owner),
    db=Depends(get_database),
):
    """The active restaurant's plan, trial and status, with this month's usage."""
    tenant_id = current_user.get("active_tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="No active tenant linked to your account.")
    tenant = await db["tenants"].find_one({"tenant_id": tenant_id}) or {"tenant_id": tenant_id}
    sub = subscription_for(tenant)
    plan_key = sub.get("plan") if sub.get("plan") in PLANS else DEFAULT_PLAN
    plan = PLANS[plan_key]
    interval = sub.get("interval") if sub.get("interval") in ("month", "year") else "month"
    price = plan["price_yearly_pkr"] if interval == "year" else plan["price_monthly_pkr"]

    trial_ends = sub.get("trial_ends_at")
    days_left = None
    if sub.get("status") == "trialing" and trial_ends:
        if trial_ends.tzinfo is None:
            trial_ends = trial_ends.replace(tzinfo=timezone.utc)
        seconds_left = (trial_ends - datetime.now(timezone.utc)).total_seconds()
        days_left = max(0, math.ceil(seconds_left / 86400))

    usage = await usage_for_tenant(db, tenant)

    # Next invoice: the plan fee for the next period, plus extra chats from this one.
    next_plan = sub.get("pending_plan") or plan_key
    extra = max(0, usage["used"] - plan["ai_conversations_per_month"]) * EXTRA_CHAT_PKR
    on_trial = sub.get("status") == "trialing"
    next_pkr = plan_fee_pkr(next_plan, interval) + (0 if on_trial else extra)
    # WhatsApp fees are billed by Meta, not Siyaf. This estimate is for the owner to see.
    meta_fee = round(max(0, usage["ai_messages"] - 1000) * 4.2)

    return SubscriptionResponse(
        pending_plan=sub.get("pending_plan"),
        pending_plan_name=PLANS[next_plan]["name"] if sub.get("pending_plan") else None,
        next_invoice_date=None if on_trial else sub.get("current_period_end"),
        next_invoice_pkr=next_pkr,
        meta_fee_pkr=meta_fee,
        plan=plan_key,
        plan_name=plan["name"],
        interval=interval,
        status=sub.get("status", "trialing"),
        trial_ends_at=trial_ends,
        trial_days_left=days_left,
        current_period_start=sub.get("current_period_start"),
        current_period_end=sub.get("current_period_end"),
        cancel_at_period_end=bool(sub.get("cancel_at_period_end")),
        price_pkr=price,
        included_chats=usage["limit"],
        extra_chat_pkr=EXTRA_CHAT_PKR,
        usage=usage,
    )


class PlanOption(BaseModel):
    key: str
    name: str
    price_monthly_pkr: int
    price_yearly_pkr: int
    ai_conversations_per_month: int
    extra_chat_pkr: int


@billing_router.get("/plans", response_model=List[PlanOption])
async def list_plans(current_user: dict = Depends(require_owner)):
    """The three plans from PRICING.md. Prices are locked."""
    return [
        PlanOption(key=key, extra_chat_pkr=EXTRA_CHAT_PKR, **{k: v for k, v in plan.items()})
        for key, plan in PLANS.items()
    ]


class CheckoutRequest(BaseModel):
    plan: Literal["basic", "standard", "pro"]
    interval: Literal["month", "year"] = "month"


class PayRequest(BaseModel):
    method: str = "card"


def _tenant_id(current_user: dict) -> str:
    tenant_id = current_user.get("active_tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="No active tenant linked to your account.")
    return tenant_id


def _payment_failed(error: str, invoice: dict) -> JSONResponse:
    # 402, and the invoice stays open so the owner can try again.
    return JSONResponse(status_code=402, content={"detail": error, "invoice_id": invoice.get("invoice_id")})


@billing_router.post("/checkout")
async def checkout(
    body: CheckoutRequest,
    current_user: dict = Depends(require_owner),
    db=Depends(get_database),
):
    """Creates the first invoice for a plan and pays it. Paying starts the subscription."""
    tenant_id = _tenant_id(current_user)
    tenant = await db["tenants"].find_one({"tenant_id": tenant_id}) or {"tenant_id": tenant_id}
    if subscription_for(tenant).get("status") == "active":
        raise HTTPException(status_code=409, detail="You already have an active plan. Plan changes come in the next update.")

    invoice = await create_subscription_invoice(db, tenant_id, body.plan, body.interval)
    paid, error = await pay_open_invoice(db, invoice)
    if error:
        return _payment_failed(error, invoice)

    tenant = await db["tenants"].find_one({"tenant_id": tenant_id}, {"subscription": 1}) or {}
    return {"invoice": paid, "subscription": tenant.get("subscription", {})}


@billing_router.post("/invoices/{invoice_id}/pay")
async def pay_invoice(
    invoice_id: str,
    body: PayRequest = PayRequest(),
    current_user: dict = Depends(require_owner),
    db=Depends(get_database),
):
    tenant_id = _tenant_id(current_user)
    invoice = await db[INVOICES].find_one({"invoice_id": invoice_id, "tenant_id": tenant_id})
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found.")
    if invoice.get("status") != "open":
        raise HTTPException(status_code=409, detail="This invoice has already been paid.")

    paid, error = await pay_open_invoice(db, invoice, method=body.method)
    if error:
        return _payment_failed(error, invoice)

    tenant = await db["tenants"].find_one({"tenant_id": tenant_id}, {"subscription": 1}) or {}
    return {"invoice": paid, "subscription": tenant.get("subscription", {})}


@billing_router.get("/invoices")
async def list_invoices(
    current_user: dict = Depends(require_owner),
    db=Depends(get_database),
):
    tenant_id = _tenant_id(current_user)
    cursor = db[INVOICES].find({"tenant_id": tenant_id}, PUBLIC_FIELDS).sort("created_at", -1).limit(50)
    return await cursor.to_list(length=50)


class ChangePlanRequest(BaseModel):
    plan: Literal["basic", "standard", "pro"]


async def _subscription_of(db, tenant_id: str) -> Dict[str, Any]:
    tenant = await db["tenants"].find_one({"tenant_id": tenant_id}, {"subscription": 1}) or {}
    return tenant.get("subscription", {})


@billing_router.post("/change-plan")
async def change_plan(
    body: ChangePlanRequest,
    current_user: dict = Depends(require_owner),
    db=Depends(get_database),
):
    """Upgrades now with a prorated invoice, paid straight away. Downgrades at the next renewal.
    Only within the same billing interval."""
    tenant_id = _tenant_id(current_user)
    tenant = await db["tenants"].find_one({"tenant_id": tenant_id}) or {"tenant_id": tenant_id}
    sub = subscription_for(tenant)
    if sub.get("status") != "active":
        raise HTTPException(status_code=409, detail="Plan changes are available while your plan is active.")
    current = sub.get("plan", DEFAULT_PLAN)
    if body.plan == current:
        raise HTTPException(status_code=409, detail="That's already your plan.")
    interval = sub.get("interval", "month")

    if plan_fee_pkr(body.plan, interval) > plan_fee_pkr(current, interval):
        now = datetime.now(timezone.utc)
        invoice = await create_upgrade_invoice(db, tenant_id, sub, body.plan, now)
        paid, error = await pay_open_invoice(db, invoice)
        if error:
            return _payment_failed(error, invoice)
        return {"invoice": paid, "subscription": await _subscription_of(db, tenant_id)}

    # Downgrade: the lower plan starts at the next renewal.
    await db["tenants"].update_one({"tenant_id": tenant_id}, {"$set": {"subscription.pending_plan": body.plan}})
    return {"invoice": None, "subscription": await _subscription_of(db, tenant_id)}


@billing_router.post("/cancel")
async def cancel_subscription(
    current_user: dict = Depends(require_owner),
    db=Depends(get_database),
):
    """Keeps everything working until the period ends, then the subscription ends."""
    tenant_id = _tenant_id(current_user)
    sub = await _subscription_of(db, tenant_id)
    if sub.get("status") not in ("active", "past_due"):
        raise HTTPException(status_code=409, detail="There's no active plan to cancel.")
    await db["tenants"].update_one({"tenant_id": tenant_id}, {"$set": {"subscription.cancel_at_period_end": True}})
    return {"subscription": await _subscription_of(db, tenant_id)}


@billing_router.post("/resume")
async def resume_subscription(
    current_user: dict = Depends(require_owner),
    db=Depends(get_database),
):
    """Undoes a cancellation that hasn't taken effect yet."""
    tenant_id = _tenant_id(current_user)
    sub = await _subscription_of(db, tenant_id)
    if not sub.get("cancel_at_period_end"):
        raise HTTPException(status_code=409, detail="Your plan isn't set to end.")
    await db["tenants"].update_one({"tenant_id": tenant_id}, {"$set": {"subscription.cancel_at_period_end": False}})
    return {"subscription": await _subscription_of(db, tenant_id)}
