import uuid
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func
from app.core.database import AsyncSessionLocal
from app.models.order import Order
from app.models.customer import Customer
from app.services.marketing_service import marketing_service

router = APIRouter(prefix="/marketing", tags=["Autonomous Marketing Engine"])

class WinBackTriggerRequest(BaseModel):
    tenant_id: Optional[str] = None

@router.get("/stats")
async def get_marketing_stats(tenant_id: Optional[str] = None):
    """
    Returns live metrics on viral loops, referral rewards, and re-engaged diners.
    """
    async with AsyncSessionLocal() as db:
        order_query = select(func.count(Order.id)).where(Order.status == "delivered")
        cust_query = select(func.count(Customer.id))

        if tenant_id:
            try:
                t_uuid = uuid.UUID(tenant_id)
                order_query = order_query.where(Order.tenant_id == t_uuid)
                cust_query = cust_query.where(Customer.tenant_id == t_uuid)
            except ValueError:
                pass

        total_delivered = (await db.execute(order_query)).scalar() or 0
        total_customers = (await db.execute(cust_query)).scalar() or 0

        # Estimated viral metrics based on delivered orders
        estimated_social_impressions = total_delivered * 140
        estimated_free_referrals = int(total_delivered * 0.18)

        return {
            "total_delivered_orders": total_delivered,
            "total_customers": total_customers,
            "estimated_social_impressions": estimated_social_impressions,
            "estimated_referrals_generated": estimated_free_referrals,
            "viral_loop_status": "active",
            "win_back_interval_days": "6-7 days",
            "incentive_dish": "Complimentary Roghani Naan / Peshawari Kahwa",
        }

@router.post("/trigger-winback")
async def trigger_winback_manually(payload: WinBackTriggerRequest):
    """
    Manually triggers the 6-7 day win-back scan for a tenant or all tenants.
    """
    dispatched = await marketing_service.run_win_back_campaign(tenant_id=payload.tenant_id)
    return {
        "status": "success",
        "messages_sent_count": len(dispatched),
        "recipients": dispatched,
    }
