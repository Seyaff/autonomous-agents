from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core.database import get_database
from middlewares.auth_middleware import require_owner
from services.billing import usage_for_tenant

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
