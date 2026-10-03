import uuid
import logging
from datetime import datetime, timezone
from typing import Literal, Optional, List, Dict, Any

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
from core.setup_state import (
    AgentSettings,
    DayHours,
    SetupState,
    apply_action,
    current_step,
    derive_locale,
    setup_of,
    validate_action,
)
from services.menu_extraction import extract_menu_items, replace_menu_items
from middlewares.auth_middleware import require_owner, require_owner_role
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
    operating_hours: Optional[List[DayHours]] = None
    min_order_amount: Optional[float] = Field(default=None, ge=0)
    delivery_areas: Optional[List[str]] = None
    payment_methods: Optional[List[Literal["cash_on_delivery", "card_on_delivery", "bank_transfer"]]] = None
    order_types: Optional[List[Literal["delivery", "takeaway", "dine_in"]]] = None


class SetupActionPayload(BaseModel):
    action: Literal["complete", "skip"]


class TenantPublic(BaseModel):
    """Allow-list of tenant fields safe to send to the browser.

    `GET /tenant/current` used to return the raw Mongo document, which
    includes `whatsapp_access_token` — every logged-in owner's browser was
    receiving their WhatsApp token in the response body. Never add a secret
    field (tokens, API keys) to this model.
    """

    tenant_id: str
    tenant_slug: Optional[str] = None
    business_name: str
    business_phone: Optional[str] = None
    address: Optional[str] = None
    currency: str = "USD"
    timezone: str = "UTC"
    whatsapp_business_id: Optional[str] = None
    phone_number_id: Optional[str] = None
    whatsapp_connected: bool = False
    display_phone_number: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    operating_hours: List[DayHours] = Field(default_factory=list)
    delivery_settings: Dict[str, Any] = Field(default_factory=dict)
    min_order_amount: float = 0.0
    delivery_areas: List[str] = Field(default_factory=list)
    payment_methods: List[str] = Field(default_factory=list)
    order_types: List[str] = Field(default_factory=list)
    agent_settings: AgentSettings = Field(default_factory=AgentSettings)
    setup: SetupState = Field(default_factory=SetupState)
    setup_current_step: str = "restaurant"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


def public_tenant(tenant: Dict[str, Any]) -> Dict[str, Any]:
    """The browser-safe view of a tenant, including where setup stands."""
    state = setup_of(tenant)
    return {
        **tenant,
        "setup": state.model_dump(),
        "setup_current_step": current_step(state),
    }


# ---------------------------------------------------------------------------
# Create tenant
# ---------------------------------------------------------------------------
@tenant_routes.post("/create")
async def create_tenant(
    payload: CreateTenantRequest,
    db=Depends(get_database),
    current_user: dict = Depends(require_owner_role),
):
    """Creates a new restaurant tenant and links it to the authenticated owner."""
    try:
        currency, timezone_name = derive_locale(payload.country)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

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
        "country": payload.country.upper(),
        "city": payload.city,
        "currency": currency,
        "timezone": timezone_name,
        "order_types": payload.order_types,
        "whatsapp_business_id": payload_data.get("whatsapp_business_id"),
        "phone_number_id": payload_data.get("phone_number_id"),
        "whatsapp_access_token": payload_data.get("whatsapp_access_token"),
        "operating_hours": [],
        "min_order_amount": 0.0,
        "delivery_areas": [],
        "payment_methods": ["cash_on_delivery"],
        "agent_settings": AgentSettings().model_dump(),
        "setup": SetupState(completed_steps=["restaurant"]).model_dump(),
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
@tenant_routes.get("/current", response_model=TenantPublic)
async def get_current_tenant(
    db=Depends(get_database),
    current_user: dict = Depends(require_owner),
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

    return TenantPublic(**public_tenant(tenant))


@tenant_routes.patch("/current")
async def update_current_tenant(
    payload: TenantUpdatePayload,
    db=Depends(get_database),
    current_user: dict = Depends(require_owner),
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
    if payload.operating_hours is not None:
        if len(payload.operating_hours) != 7 or len({h.day for h in payload.operating_hours}) != 7:
            raise HTTPException(status_code=400, detail="operating_hours needs one entry for each day of the week.")
        update_fields["operating_hours"] = [h.model_dump() for h in payload.operating_hours]
    if payload.min_order_amount is not None:
        update_fields["min_order_amount"] = payload.min_order_amount
    if payload.delivery_areas is not None:
        update_fields["delivery_areas"] = [a.strip() for a in payload.delivery_areas if a.strip()][:50]
    if payload.payment_methods is not None:
        if not payload.payment_methods:
            raise HTTPException(status_code=400, detail="Choose at least one payment method.")
        update_fields["payment_methods"] = payload.payment_methods
    if payload.order_types is not None:
        if not payload.order_types:
            raise HTTPException(status_code=400, detail="Choose at least one order type.")
        update_fields["order_types"] = payload.order_types

    await db.tenants.update_one({"tenant_id": tenant_id}, {"$set": update_fields})
    return {"status": "success", "message": "Restaurant settings updated."}


@tenant_routes.patch("/current/agent-settings", response_model=AgentSettings)
async def update_agent_settings(
    payload: AgentSettings,
    db=Depends(get_database),
    current_user: dict = Depends(require_owner),
):
    """Reply language, tone, greeting and which situations go to the owner."""
    tenant_id = current_user.get("active_tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="No active tenant found.")
    await db.tenants.update_one(
        {"tenant_id": tenant_id},
        {"$set": {"agent_settings": payload.model_dump(), "updated_at": datetime.now(timezone.utc)}},
    )
    return payload


# Setup progress. The finish route is declared before the step route, so the
# word "finish" isn't matched as a step name.
@tenant_routes.post("/current/setup/finish", response_model=SetupState)
async def finish_setup(
    db=Depends(get_database),
    current_user: dict = Depends(require_owner),
):
    """Marks setup complete. Only this endpoint sets the owner's is_onboarded flag."""
    tenant_id = current_user.get("active_tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="No active tenant found.")
    tenant = await db.tenants.find_one({"tenant_id": tenant_id})
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant record not found.")

    state = setup_of(tenant)
    if current_step(state) != "done":
        raise HTTPException(status_code=409, detail="Finish every step, or skip the optional ones, first.")

    now = datetime.now(timezone.utc)
    state.completed_at = state.completed_at or now
    await db.tenants.update_one(
        {"tenant_id": tenant_id},
        {"$set": {"setup": state.model_dump(), "updated_at": now}},
    )
    await db.users.update_one(
        {"user_id": current_user["user_id"]},
        {"$set": {"is_onboarded": True, "updated_at": now}},
    )
    return state


@tenant_routes.post("/current/setup/{step}", response_model=SetupState)
async def update_setup_step(
    step: str,
    payload: SetupActionPayload,
    db=Depends(get_database),
    current_user: dict = Depends(require_owner),
):
    """Completes or skips one setup step. Required steps must be done in order."""
    tenant_id = current_user.get("active_tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="No active tenant found.")
    tenant = await db.tenants.find_one({"tenant_id": tenant_id})
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant record not found.")

    state = setup_of(tenant)
    problem = validate_action(state, step, payload.action)
    if problem:
        raise HTTPException(status_code=problem[0], detail=problem[1])

    new_state = apply_action(state, step, payload.action)
    await db.tenants.update_one(
        {"tenant_id": tenant_id},
        {"$set": {"setup": new_state.model_dump(), "updated_at": datetime.now(timezone.utc)}},
    )
    return new_state


@tenant_routes.get("/current/menu-items")
async def list_menu_items(
    db=Depends(get_database),
    current_user: dict = Depends(require_owner),
):
    """Dishes extracted from the most recent menu upload."""
    tenant_id = current_user.get("active_tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="No active tenant found.")

    rows = await db["menu_items"].find(
        {"tenant_id": tenant_id},
        {"_id": 0, "name": 1, "category": 1, "price": 1, "description": 1, "doc_id": 1},
    ).sort([("category", 1), ("name", 1)]).to_list(length=500)

    source_filename = None
    if rows:
        doc = await db["tenant_knowledge"].find_one(
            {"tenant_id": tenant_id, "doc_id": rows[0]["doc_id"]}, {"title": 1}
        )
        source_filename = (doc or {}).get("title")
    for row in rows:
        row.pop("doc_id", None)

    return {"items": rows, "source_filename": source_filename}


# ---------------------------------------------------------------------------
# Meta embedded signup
# ---------------------------------------------------------------------------
@tenant_routes.post("/meta-embedded-signup")
async def connect_meta_whatsapp(
    payload: MetaEmbeddedSignupPayload,
    db=Depends(get_database),
    current_user: dict = Depends(require_owner),
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
    current_user: dict = Depends(require_owner),
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

    # The menu is searchable now. Reading out the dishes is a second step; if
    # it fails the upload still counts, and the owner can retry the list.
    full_text = result.pop("full_text", "")
    try:
        items = await extract_menu_items(full_text)
        result["items_found"] = await replace_menu_items(db, tenant_id, result["doc_id"], items)
    except Exception as e:
        logger.error(f"[upload-menu-pdf] dish extraction failed tenant={tenant_id}: {e}")
        result["items_found"] = 0
        result["items_error"] = "The menu is saved for the agent, but we couldn't read the dishes. Try again."

    logger.info(
        f"[upload-menu-pdf] tenant={tenant_id} "
        f"chunks={result.get('chunks_indexed')} items={result.get('items_found')} doc_id={result.get('doc_id')}"
    )
    return result
