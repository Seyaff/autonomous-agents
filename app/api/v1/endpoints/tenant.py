import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

import httpx
from fastapi import (
    APIRouter,
    Response,
    HTTPException,
    status,
    Depends,
    UploadFile,
    File,
)
from pydantic import BaseModel, Field


from core.database import get_database
from core.settings import settings
from middlewares.auth_middleware import get_current_user
from schemas.models import CreateTenantRequest

# ---- pick the module you actually have ----
# If the file is services/pdf_ingestion.py → use this:
from services.knowledge_ingestion import ingest_pdf_bytes_for_tenant

# If you renamed it to services/knowledge_ingestion.py → use that instead:
# from services.knowledge_ingestion import ingest_pdf_bytes_for_tenant

logger = logging.getLogger(__name__)

tenant_routes = APIRouter(prefix="/tenant", tags=["Tenant Routes"])


class MetaEmbeddedSignupPayload(BaseModel):
    code: str = Field(..., description="Meta authorization code from embedded signup popup")
    waba_id: Optional[str] = Field(None, description="WhatsApp Business Account ID")
    phone_number_id: Optional[str] = Field(None, description="Phone number ID")


class TenantUpdatePayload(BaseModel):
    business_name: Optional[str] = None
    business_phone: Optional[str] = None
    address: Optional[str] = None
    currency: Optional[str] = None
    flat_delivery_fee: Optional[float] = None
    avg_prep_time_minutes: Optional[int] = None


# ---------------------------------------------------------------------------
# Create tenant
# ---------------------------------------------------------------------------
@tenant_routes.post("/create")
async def create_tenant(
    payload: CreateTenantRequest,
    db=Depends(get_database),
    current_user: dict = Depends(get_current_user),
):
    """Creates a new restaurant tenant and links it to the authenticated owner."""
    slug = payload.business_name.lower().replace(" ", "-")[:20]
    tenant_id = f"res_{slug.replace('-', '_')}_{str(uuid.uuid4())[:4]}"

    user_mongo_id = current_user.get("_id")
    user_custom_id = current_user.get("user_id")

    payload_data = payload.model_dump()

    tenant_doc = {
        "tenant_id": tenant_id,
        "tenant_slug": slug,
        "owner_id": user_mongo_id,
        "business_name": payload_data["business_name"],
        "business_phone": payload_data.get("business_phone"),
        "address": payload_data.get("address"),
        "currency": payload_data.get("currency", "USD"),
        "timezone": payload_data.get("timezone", "UTC"),
        "whatsapp_business_id": payload_data.get("whatsapp_business_id"),
        "phone_number_id": payload_data.get("phone_number_id"),
        "whatsapp_access_token": payload_data.get("whatsapp_access_token"),
        "operating_hours": payload_data.get("operating_hours", []),
        "delivery_settings": {
            "supports_delivery": True,
            "supports_takeaway": True,
            "supports_reservations": True,
            "flat_delivery_fee": 0.0,
            "avg_prep_time_minutes": 30,
        },
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }

    await db.tenants.insert_one(tenant_doc)

    await db.users.update_one(
        {"user_id": user_custom_id},
        {
            "$set": {
                "active_tenant_id": tenant_id,
                "is_onboarded": True,
                "updated_at": datetime.now(timezone.utc),
            },
            "$addToSet": {"tenants": tenant_id},
        },
    )

    return {
        "status": "success",
        "message": "Tenant successfully created.",
        "tenant_id": tenant_id,
        "next_step": 2,
    }


# ---------------------------------------------------------------------------
# Get / update current tenant
# ---------------------------------------------------------------------------
@tenant_routes.get("/current")
async def get_current_tenant(
    db=Depends(get_database),
    current_user: dict = Depends(get_current_user),
):
    """Retrieves the active tenant details for the logged-in owner."""
    tenant_id = current_user.get("active_tenant_id")
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active restaurant profile found. Please complete onboarding.",
        )

    tenant = await db.tenants.find_one({"tenant_id": tenant_id})
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant record not found.")

    if "_id" in tenant:
        tenant["_id"] = str(tenant["_id"])
    return tenant


@tenant_routes.patch("/current")
async def update_current_tenant(
    payload: TenantUpdatePayload,
    db=Depends(get_database),
    current_user: dict = Depends(get_current_user),
):
    """Updates operational settings for the current active tenant."""
    tenant_id = current_user.get("active_tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="No active tenant found.")

    update_fields: Dict[str, Any] = {"updated_at": datetime.now(timezone.utc)}
    if payload.business_name:
        update_fields["business_name"] = payload.business_name
    if payload.business_phone:
        update_fields["business_phone"] = payload.business_phone
    if payload.address:
        update_fields["address"] = payload.address
    if payload.currency:
        update_fields["currency"] = payload.currency

    if payload.flat_delivery_fee is not None:
        update_fields["delivery_settings.flat_delivery_fee"] = payload.flat_delivery_fee
    if payload.avg_prep_time_minutes is not None:
        update_fields["delivery_settings.avg_prep_time_minutes"] = payload.avg_prep_time_minutes

    await db.tenants.update_one({"tenant_id": tenant_id}, {"$set": update_fields})
    return {"status": "success", "message": "Restaurant settings updated."}


# ---------------------------------------------------------------------------
# Meta embedded signup
# ---------------------------------------------------------------------------
@tenant_routes.post("/meta-embedded-signup")
async def connect_meta_whatsapp(
    payload: MetaEmbeddedSignupPayload,
    db=Depends(get_database),
    current_user: dict = Depends(get_current_user),
):
    """
    Exchanges Meta Embedded Signup authorization code for a long-lived access token,
    registers the phone number ID, and connects the WhatsApp Business Account (WABA) to the tenant.
    """
    tenant_id = current_user.get("active_tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="Create a restaurant profile first.")

    app_id = settings.META_APP_ID
    app_secret = settings.META_APP_SECRET

    access_token = None
    if app_id and app_secret and payload.code:
        token_exchange_url = "https://graph.facebook.com/v19.0/oauth/access_token"
        params = {
            "client_id": app_id,
            "client_secret": app_secret,
            "code": payload.code,
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.get(token_exchange_url, params=params)
                if resp.status_code == 200:
                    access_token = resp.json().get("access_token")
                else:
                    logger.warning(f"Meta token exchange failed: {resp.text}")
            except Exception as e:
                logger.error(f"Error during Meta token exchange: {e}")

    final_token = access_token or settings.WHATSAPP_TOKEN
    waba_id = payload.waba_id or settings.WHATSAPP_BUSINESS_ACCOUNT_ID
    phone_id = payload.phone_number_id or settings.WHATSAPP_PHONE_NUMBER_ID

    update_doc = {
        "whatsapp_business_id": waba_id,
        "phone_number_id": phone_id,
        "whatsapp_access_token": final_token,
        "whatsapp_connected": True,
        "updated_at": datetime.now(timezone.utc),
    }

    await db.tenants.update_one({"tenant_id": tenant_id}, {"$set": update_doc})

    return {
        "status": "success",
        "message": "WhatsApp Business Account linked successfully!",
        "phone_number_id": phone_id,
        "waba_id": waba_id,
    }


# ---------------------------------------------------------------------------
# PDF menu    ← moved OUT of the function above, into its own top-level route
# ---------------------------------------------------------------------------
@tenant_routes.post("/upload-menu-pdf")
async def upload_menu_pdf(
    file: UploadFile = File(...),
    db=Depends(get_database),
    current_user: dict = Depends(get_current_user),
):
    """
    Accepts a PDF menu upload from the onboarding/dashboard and indexes it into
    the tenant's Pinecone namespace for RAG retrieval.
    """
    tenant_id = current_user.get("active_tenant_id")
    if not tenant_id:
        raise HTTPException(
            status_code=400,
            detail="No active tenant. Complete profile setup first.",
        )

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Empty file upload.")

    logger.info(
        f"[upload-menu-pdf] user={current_user.get('user_id')} "
        f"tenant={tenant_id} file={file.filename} bytes={len(file_bytes)}"
    )

    result = await ingest_pdf_bytes_for_tenant(
        file_bytes=file_bytes,
        filename=file.filename,
        tenant_id=tenant_id,
    )

    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result["message"])

    logger.info(
        f"[upload-menu-pdf] ✅ tenant={tenant_id} "
        f"chunks={result.get('chunks_indexed')} doc_id={result.get('doc_id')}"
    )
    return result
