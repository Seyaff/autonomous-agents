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
    pay_open_invoice,
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
    return SubscriptionResponse(
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
