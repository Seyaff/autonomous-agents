import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status

from core.database import get_database
from middlewares.auth_middleware import require_owner
from agents.analytics.weekly_report import compile_and_send_weekly_report, generate_7day_analytics

logger = logging.getLogger(__name__)

analytics_router = APIRouter(prefix="/analytics", tags=["Analytics & BI"])


@analytics_router.get("/7day-summary")
async def get_7day_summary(
    current_user: dict = Depends(require_owner)
):
    """Calculates live trailing 7-day operational & revenue metrics for active tenant."""
    tenant_id = current_user.get("active_tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="No active tenant linked to user.")

    metrics = await generate_7day_analytics(tenant_id)
    return {"status": "success", "metrics": metrics}


@analytics_router.get("/weekly-reports")
async def list_weekly_reports(
    current_user: dict = Depends(require_owner),
    db = Depends(get_database)
):
    """Lists past autonomous weekly executive reports for the active tenant."""
    tenant_id = current_user.get("active_tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="No active tenant linked to user.")

    cursor = db["weekly_reports"].find({"tenant_id": tenant_id}).sort("created_at", -1)
    reports = await cursor.to_list(length=50)

    for r in reports:
        if "_id" in r:
            r["_id"] = str(r["_id"])

    return {"status": "success", "reports": reports}


@analytics_router.post("/weekly/generate")
async def trigger_weekly_report(
    current_user: dict = Depends(require_owner)
):
    """
    Manually triggers the 7-Day Autopilot Business Intelligence Agent.
    Aggregates performance, compiles executive insights, and proactively notifies the owner on WhatsApp.
    """
    tenant_id = current_user.get("active_tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="No active tenant linked to user.")

    report = await compile_and_send_weekly_report(tenant_id)
    return {
        "status": "success",
        "message": "Weekly Autopilot report generated and dispatched.",
        "report": report
    }
