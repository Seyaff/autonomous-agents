import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import ValidationError

from core.database import get_database
from middlewares.auth_middleware import require_owner
from services.campaigns import (
    CAMPAIGNS,
    RECIPIENTS,
    Audience,
    CampaignCreate,
    create_campaign,
    public_campaign,
    resolve_audience,
    start_campaign,
)
from services.templates import (
    LANGUAGES,
    ORDER_UPDATE_TEMPLATE,
    TEMPLATES,
    TemplateDraft,
    find_template,
    order_update_draft,
    public_template,
    remove_template,
    submit_template,
    sync_templates,
)

logger = logging.getLogger(__name__)

templates_router = APIRouter(prefix="/templates", tags=["WhatsApp templates"])
campaigns_router = APIRouter(prefix="/campaigns", tags=["Campaigns"])


async def _tenant(db, current_user: dict) -> Dict[str, Any]:
    tenant_id = current_user.get("active_tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="No active business found.")
    tenant = await db.tenants.find_one({"tenant_id": tenant_id})
    if not tenant:
        raise HTTPException(status_code=404, detail="Business record not found.")
    return tenant


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------
@templates_router.get("")
async def list_my_templates(
    status: Optional[str] = Query(None, description="Only templates with this status, e.g. APPROVED"),
    db=Depends(get_database),
    current_user: dict = Depends(require_owner),
):
    """The business's templates as last synced from Meta."""
    tenant = await _tenant(db, current_user)
    query: Dict[str, Any] = {"tenant_id": tenant["tenant_id"]}
    if status:
        query["status"] = status.upper()
    rows = await db[TEMPLATES].find(query).sort([("name", 1), ("language", 1)]).to_list(length=1000)
    return {
        "templates": [public_template(r) for r in rows],
        "synced_at": tenant.get("templates_synced_at"),
        "languages": LANGUAGES,
        "whatsapp_connected": bool(tenant.get("whatsapp_business_id") and tenant.get("whatsapp_access_token")),
    }


@templates_router.post("/sync")
async def sync_my_templates(db=Depends(get_database), current_user: dict = Depends(require_owner)):
    """Fetches every template and its review status from Meta."""
    tenant = await _tenant(db, current_user)
    try:
        docs = await sync_templates(db, tenant)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return {"templates": [public_template(d) for d in docs], "synced_at": datetime.now(timezone.utc)}


@templates_router.post("", status_code=201)
async def create_my_template(
    draft: TemplateDraft,
    db=Depends(get_database),
    current_user: dict = Depends(require_owner),
):
    """Submits a new template for Meta's review. Review usually takes minutes, sometimes a day."""
    tenant = await _tenant(db, current_user)
    try:
        doc = await submit_template(db, tenant, draft)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"template": public_template(doc)}


@templates_router.delete("/{name}")
async def delete_my_template(
    name: str,
    language: str = Query(...),
    db=Depends(get_database),
    current_user: dict = Depends(require_owner),
):
    tenant = await _tenant(db, current_user)
    try:
        await remove_template(db, tenant, name, language)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "deleted"}


@templates_router.get("/order-updates")
async def order_updates_status(db=Depends(get_database), current_user: dict = Depends(require_owner)):
    """Whether order and booking updates can still reach customers after 24 hours."""
    tenant = await _tenant(db, current_user)
    chosen = (tenant.get("template_settings") or {}).get("order_updates") or {}
    doc = None
    if chosen.get("name"):
        doc = await find_template(db, tenant["tenant_id"], chosen["name"], chosen.get("language") or "en")
    return {"template": public_template(doc) if doc else None, "configured": bool(chosen.get("name"))}


@templates_router.post("/order-updates")
async def set_up_order_updates(
    language: str = Query("en"),
    db=Depends(get_database),
    current_user: dict = Depends(require_owner),
):
    """Submits the standard order-update template (or reuses it if it exists) and uses it from now on."""
    tenant = await _tenant(db, current_user)
    try:
        draft = order_update_draft(language)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=e.errors()[0]["msg"])
    doc = await find_template(db, tenant["tenant_id"], ORDER_UPDATE_TEMPLATE, draft.language)
    if not doc or doc.get("status") in ("REJECTED", "DISABLED"):
        try:
            if doc:
                await remove_template(db, tenant, ORDER_UPDATE_TEMPLATE, draft.language)
            doc = await submit_template(db, tenant, draft)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    await db.tenants.update_one(
        {"tenant_id": tenant["tenant_id"]},
        {"$set": {
            "template_settings.order_updates": {"name": ORDER_UPDATE_TEMPLATE, "language": draft.language},
            "updated_at": datetime.now(timezone.utc),
        }},
    )
    return {"template": public_template(doc), "configured": True}


# ---------------------------------------------------------------------------
# Campaigns
# ---------------------------------------------------------------------------
@campaigns_router.get("")
async def list_campaigns(db=Depends(get_database), current_user: dict = Depends(require_owner)):
    tenant = await _tenant(db, current_user)
    rows = await db[CAMPAIGNS].find({"tenant_id": tenant["tenant_id"]}).sort("created_at", -1).to_list(length=200)
    return {"campaigns": [public_campaign(r) for r in rows]}


@campaigns_router.post("/audience")
async def preview_audience(audience: Audience, db=Depends(get_database), current_user: dict = Depends(require_owner)):
    """How many customers a campaign would reach, before it is sent."""
    tenant = await _tenant(db, current_user)
    recipients, skipped = await resolve_audience(db, tenant["tenant_id"], audience)
    return {"count": len(recipients), "skipped_opted_out": skipped, "sample": [r["name"] or r["phone"] for r in recipients[:5]]}


@campaigns_router.post("", status_code=201)
async def send_campaign(payload: CampaignCreate, db=Depends(get_database), current_user: dict = Depends(require_owner)):
    """Saves the campaign and starts sending it in the background."""
    tenant = await _tenant(db, current_user)
    try:
        campaign = await create_campaign(db, tenant, payload, current_user.get("user_id"))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    start_campaign(db, tenant, campaign["campaign_id"])
    return {"campaign": public_campaign(campaign)}


@campaigns_router.get("/{campaign_id}")
async def get_campaign(campaign_id: str, db=Depends(get_database), current_user: dict = Depends(require_owner)):
    """The campaign's totals, and the recipients it couldn't reach with the reason."""
    tenant = await _tenant(db, current_user)
    campaign = await db[CAMPAIGNS].find_one({"campaign_id": campaign_id, "tenant_id": tenant["tenant_id"]})
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found.")
    failed = await db[RECIPIENTS].find(
        {"campaign_id": campaign_id, "status": "failed"}, {"_id": 0, "phone": 1, "name": 1, "error": 1}
    ).to_list(length=100)
    return {"campaign": public_campaign(campaign), "failed": failed}


@campaigns_router.post("/{campaign_id}/resume")
async def resume_campaign(campaign_id: str, db=Depends(get_database), current_user: dict = Depends(require_owner)):
    """Carries on sending to the recipients not reached yet, after a pause or a server restart."""
    tenant = await _tenant(db, current_user)
    campaign = await db[CAMPAIGNS].find_one({"campaign_id": campaign_id, "tenant_id": tenant["tenant_id"]})
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found.")
    if campaign.get("status") in ("done", "failed"):
        raise HTTPException(status_code=409, detail="This campaign has finished.")
    if campaign.get("status") == "sending" and not public_campaign(campaign)["stalled"]:
        raise HTTPException(status_code=409, detail="This campaign is still sending.")
    now = datetime.now(timezone.utc)
    await db[CAMPAIGNS].update_one(
        {"campaign_id": campaign_id}, {"$set": {"status": "sending", "error": None, "updated_at": now}}
    )
    start_campaign(db, tenant, campaign_id)
    return {"status": "sending"}
