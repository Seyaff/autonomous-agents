import os
import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from core.database import get_database
from middlewares.auth_middleware import get_current_user
from agents.founder.lead_generator import run_autonomous_lead_pipeline
from agents.founder.outreach_agent import draft_personalized_pitch, process_inbound_lead_reply

logger = logging.getLogger(__name__)

founder_router = APIRouter(prefix="/founder", tags=["Founder Growth Engine"])


class LeadHuntRequest(BaseModel):
    query: str = Field(..., example="Scrape top real estate agencies in Florida and analyze their customer response")
    max_leads: int = Field(15, ge=5, le=50)


class DraftPitchRequest(BaseModel):
    company_name: str
    website: Optional[str] = None
    fit_reason: Optional[str] = None
    recommended_pitch_angle: Optional[str] = None


class LeadReplyRequest(BaseModel):
    sender: str = Field(..., description="Phone number or email of replying lead")
    message: str = Field(..., description="The raw reply received from the prospect")
    founder_whatsapp: Optional[str] = Field(None, description="Founder phone to alert")


@founder_router.post("/lead-hunt")
async def trigger_autonomous_lead_hunt(
    payload: LeadHuntRequest,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_database)
):
    """
    Triggers the Autonomous Lead Generation Agent:
    - Scrapes & searches targeted businesses
    - Classifies them as Warm, Hot, or Premium
    - Exports directly to styled Excel (.xlsx) file
    - Saves campaign to database
    """
    user_id = current_user.get("user_id")
    result = await run_autonomous_lead_pipeline(
        task_prompt=payload.query,
        user_id=user_id,
        max_leads=payload.max_leads
    )
    return result


@founder_router.get("/campaigns")
async def list_founder_campaigns(
    current_user: dict = Depends(get_current_user),
    db = Depends(get_database)
):
    """Lists all past lead hunting campaigns with metrics and export links."""
    user_id = current_user.get("user_id")
    cursor = db["lead_campaigns"].find({"founder_id": user_id}).sort("created_at", -1)
    campaigns = await cursor.to_list(length=100)

    for c in campaigns:
        if "_id" in c:
            c["_id"] = str(c["_id"])
    return campaigns


@founder_router.get("/campaigns/{campaign_id}/export")
async def download_campaign_excel(
    campaign_id: str,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_database)
):
    """Downloads the generated Excel spreadsheet (.xlsx) for the campaign."""
    campaign = await db["lead_campaigns"].find_one({"campaign_id": campaign_id})
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    filepath = campaign.get("export_filepath")
    if not filepath or not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Excel export file not found on disk")

    filename = campaign.get("filename", f"{campaign_id}.xlsx")
    return FileResponse(
        path=filepath,
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


@founder_router.post("/outreach/draft")
async def draft_outreach_pitch(
    payload: DraftPitchRequest,
    current_user: dict = Depends(get_current_user)
):
    """Drafts personalized cold email and WhatsApp outreach for a specific lead."""
    founder_name = current_user.get("full_name", "Founder")
    lead_dict = payload.model_dump()
    pitch = await draft_personalized_pitch(lead=lead_dict, founder_name=founder_name)
    return {
        "status": "success",
        "company": payload.company_name,
        "pitch": pitch
    }


@founder_router.post("/reply-handler")
async def handle_prospect_reply(
    payload: LeadReplyRequest,
    db = Depends(get_database)
):
    """
    Processes an incoming reply from an outreach prospect.
    Evaluates intent, drafts smart objection handling / scheduling response,
    and proactively alerts the founder.
    """
    analysis = await process_inbound_lead_reply(
        sender_identifier=payload.sender,
        reply_message=payload.message,
        founder_whatsapp=payload.founder_whatsapp
    )
    return {
        "status": "success",
        "analysis": analysis
    }
