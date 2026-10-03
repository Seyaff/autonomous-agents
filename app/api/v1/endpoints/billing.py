from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core.database import get_database
from middlewares.auth_middleware import require_owner
import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

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
