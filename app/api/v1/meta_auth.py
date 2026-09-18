import uuid
import logging
import httpx
from typing import Optional
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from app.config import settings
from app.core.database import AsyncSessionLocal
from app.models.tenant import Tenant

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/meta", tags=["Meta Embedded Signup & Auth"])

class EmbeddedSignupRequest(BaseModel):
    tenant_id: str
    code: str
    waba_id: Optional[str] = None
    phone_number_id: Optional[str] = None

@router.post("/embedded-signup/callback")
async def handle_embedded_signup(payload: EmbeddedSignupRequest):
    """
    Exchanges Meta authorization code from Embedded Signup for a permanent access token
    and links the restaurant's WABA and phone_number_id.
    """
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(Tenant).where(Tenant.id == uuid.UUID(payload.tenant_id)))
        tenant = res.scalar_one_or_none()
        if not tenant:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

        # If Meta App Secret is configured, perform exchange with Meta Graph API
        access_token = "mock_access_token_dev"
        if settings.META_APP_ID and settings.META_APP_SECRET:
            token_url = f"{settings.META_GRAPH_URL}/{settings.META_API_VERSION}/oauth/access_token"
            params = {
                "client_id": settings.META_APP_ID,
                "client_secret": settings.META_APP_SECRET,
                "code": payload.code
            }
            async with httpx.AsyncClient() as client:
                try:
                    resp = await client.get(token_url, params=params, timeout=10.0)
                    resp.raise_for_status()
                    data = resp.json()
                    access_token = data.get("access_token", access_token)
                except Exception as e:
                    logger.error(f"Failed to exchange Meta OAuth code: {e}")
                    raise HTTPException(status_code=400, detail="Meta OAuth exchange failed")

        tenant.waba_id = payload.waba_id or tenant.waba_id
        tenant.phone_number_id = payload.phone_number_id or tenant.phone_number_id
        tenant.meta_access_token = access_token
        tenant.is_active = True
        await db.commit()

        return {
            "status": "connected",
            "tenant_id": str(tenant.id),
            "phone_number_id": tenant.phone_number_id,
            "message": "WhatsApp Business Account connected successfully via Embedded Signup!"
        }
