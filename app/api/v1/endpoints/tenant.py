import uuid
import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
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
import re

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
from services.billing import new_subscription
from services.availability import today_for
from services.menu_extraction import extract_menu_items, replace_menu_items
from services.menu_jobs import MENU_JOBS, active_job, create_job, mark_stale_jobs, public, start_job
from core.secrets import protect
from core.whatsapp_utils import subscribe_business_account, verify_phone_number
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
    timezone: Optional[str] = None
    operating_hours: Optional[List[DayHours]] = None
    min_order_amount: Optional[float] = Field(default=None, ge=0)
    delivery_areas: Optional[List[str]] = None
    payment_methods: Optional[List[Literal["cash_on_delivery", "card_on_delivery", "bank_transfer"]]] = None
    order_types: Optional[List[Literal["delivery", "takeaway", "dine_in"]]] = None


class AgentTogglePayload(BaseModel):
    enabled: bool


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
    whatsapp_status: str = "disconnected"
    whatsapp_last_error: Optional[str] = None
    verified_name: Optional[str] = None
    agent_enabled: bool = True
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
        "whatsapp_access_token": protect(payload_data.get("whatsapp_access_token")),
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
        "subscription": new_subscription(),
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
    if payload.timezone:
        try:
            ZoneInfo(payload.timezone)
        except ZoneInfoNotFoundError:
            raise HTTPException(status_code=400, detail=f"Unknown timezone: {payload.timezone}")
        update_fields["timezone"] = payload.timezone

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


@tenant_routes.patch("/current/agent")
async def set_agent_enabled(
    payload: AgentTogglePayload,
    db=Depends(get_database),
    current_user: dict = Depends(require_owner),
):
    """Pauses or resumes the customer-support agent for the whole restaurant.
    While paused, customers still reach the inbox, and the owner replies by hand."""
    tenant_id = current_user.get("active_tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="No active tenant found.")

    await db.tenants.update_one(
        {"tenant_id": tenant_id},
        {"$set": {"agent_enabled": payload.enabled, "updated_at": datetime.now(timezone.utc)}},
    )
    return {"status": "success", "agent_enabled": payload.enabled}


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
    # The WhatsApp step only counts as done once the number is really connected.
    if step == "whatsapp" and payload.action == "complete" and not (tenant.get("whatsapp_connected") and tenant.get("phone_number_id")):
        raise HTTPException(status_code=409, detail="Connect your WhatsApp number first. Your agent can't reply until it's connected.")

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

    tenant = await db.tenants.find_one({"tenant_id": tenant_id}, {"timezone": 1}) or {}
    today = today_for(tenant)
    rows = await db["menu_items"].find(
        {"tenant_id": tenant_id},
        {"_id": 0, "name": 1, "category": 1, "price": 1, "description": 1, "doc_id": 1, "sold_out_on": 1},
    ).sort([("category", 1), ("name", 1)]).to_list(length=500)

    source_filename = None
    if rows:
        doc = await db["tenant_knowledge"].find_one(
            {"tenant_id": tenant_id, "doc_id": rows[0]["doc_id"]}, {"title": 1}
        )
        source_filename = (doc or {}).get("title")
    for row in rows:
        row.pop("doc_id", None)
        row["sold_out_today"] = row.pop("sold_out_on", None) == today

    return {"items": rows, "source_filename": source_filename}


class SoldOutPayload(BaseModel):
    name: str
    sold_out: bool


@tenant_routes.post("/current/menu-items/sold-out")
async def set_sold_out(
    payload: SoldOutPayload,
    db=Depends(get_database),
    current_user: dict = Depends(require_owner),
):
    """Marks a dish sold out for today, or back in. It returns to the menu on its own tomorrow."""
    tenant_id = current_user.get("active_tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="No active tenant found.")
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name the dish.")

    tenant = await db.tenants.find_one({"tenant_id": tenant_id}, {"timezone": 1}) or {}
    # Case-insensitive match on the dish name, so "chicken karahi" matches "Chicken Karahi".
    match = {"tenant_id": tenant_id, "name": {"$regex": f"^{re.escape(name)}$", "$options": "i"}}
    if payload.sold_out:
        update = {"$set": {"sold_out_on": today_for(tenant)}}
    else:
        update = {"$unset": {"sold_out_on": ""}}
    result = await db["menu_items"].update_many(match, update)
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="That dish isn't on your menu.")
    return {"name": name, "sold_out_today": payload.sold_out, "dishes_updated": result.matched_count}


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
    Connects this restaurant's own WhatsApp number.

    Every step must succeed: exchange the signup code for a token, check the token
    can read the number, check the number isn't used by another restaurant, and
    subscribe the business account to our webhook. If any step fails, nothing falls
    back to shared credentials. The restaurant is marked as errored with the reason,
    so the owner sees it.
    """
    tenant_id = current_user.get("active_tenant_id")
    logger.info(
        f"[meta-signup] start tenant={tenant_id} waba={payload.waba_id} "
        f"phone_number_id={payload.phone_number_id} has_code={bool(payload.code)}"
    )
    if not tenant_id:
        raise HTTPException(status_code=400, detail="Create a restaurant profile first.")

    if not (settings.META_APP_ID and settings.META_APP_SECRET):
        raise HTTPException(
            status_code=503,
            detail="WhatsApp connection isn't set up on the server yet. Use the shared test number for now.",
        )
    if not payload.phone_number_id or not payload.waba_id:
        raise HTTPException(
            status_code=400,
            detail="Meta didn't return the phone number or business account. Try connecting again.",
        )

    async def fail(message: str, status_code: int = 400):
        logger.warning(f"[meta-signup] failed tenant={tenant_id} status={status_code}: {message}")
        await db.tenants.update_one(
            {"tenant_id": tenant_id},
            {"$set": {
                "whatsapp_status": "error",
                "whatsapp_last_error": message,
                "whatsapp_checked_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }},
        )
        raise HTTPException(status_code=status_code, detail=message)

    token = await _exchange_signup_code(payload.code)
    if not token:
        await fail("Meta didn't accept the signup. Try connecting again.")
    logger.info(f"[meta-signup] code exchanged tenant={tenant_id}")

    other = await db.tenants.find_one(
        {"phone_number_id": payload.phone_number_id, "tenant_id": {"$ne": tenant_id}},
        {"tenant_id": 1},
    )
    if other:
        await fail("This number is already connected to another restaurant.", status_code=409)

    try:
        details = await verify_phone_number(token, payload.phone_number_id)
        logger.info(f"[meta-signup] number verified tenant={tenant_id} display={details.get('display_phone_number')}")
        await subscribe_business_account(token, payload.waba_id)
        logger.info(f"[meta-signup] waba subscribed tenant={tenant_id}")
    except ValueError as e:
        await fail(str(e))

    now = datetime.now(timezone.utc)
    await db.tenants.update_one(
        {"tenant_id": tenant_id},
        {"$set": {
            "whatsapp_business_id": payload.waba_id,
            "phone_number_id": payload.phone_number_id,
            "whatsapp_access_token": protect(token),
            "whatsapp_connected": True,
            "whatsapp_status": "connected",
            "whatsapp_last_error": None,
            "whatsapp_checked_at": now,
            "display_phone_number": details.get("display_phone_number"),
            "verified_name": details.get("verified_name"),
            "updated_at": now,
        }},
    )

    return {
        "status": "success",
        "message": "WhatsApp connected.",
        "phone_number_id": payload.phone_number_id,
        "waba_id": payload.waba_id,
        "display_phone_number": details.get("display_phone_number"),
        "verified_name": details.get("verified_name"),
    }


async def _exchange_signup_code(code: str) -> Optional[str]:
    """Exchanges the Embedded Signup code for an access token. None if Meta refuses it."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.get(
                "https://graph.facebook.com/v19.0/oauth/access_token",
                params={
                    "client_id": settings.META_APP_ID,
                    "client_secret": settings.META_APP_SECRET,
                    "code": code,
                },
            )
        except httpx.RequestError as e:
            logger.error(f"Meta token exchange could not be reached: {e}")
            return None
    if resp.status_code != 200:
        logger.warning(f"Meta token exchange failed: {resp.text}")
        return None
    return resp.json().get("access_token")


# ---------------------------------------------------------------------------
# PDF menu    ← moved OUT of the function above, into its own top-level route
# ---------------------------------------------------------------------------
@tenant_routes.post("/upload-menu-pdf", status_code=202)
async def upload_menu_pdf(
    file: UploadFile = File(...),
    db=Depends(get_database),
    current_user: dict = Depends(require_owner),
):
    """
    Accepts a PDF menu and starts reading it in the background. Returns a job at
    once. Poll GET /tenant/menu-uploads/{job_id} for progress.
    """
    tenant_id = current_user.get("active_tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="No active restaurant. Create the restaurant first.")

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF menus are supported for now.")

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="That file is empty.")
    if len(file_bytes) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="That file is over 20 MB. Try a smaller PDF.")

    await mark_stale_jobs(db, tenant_id)
    busy = await active_job(db, tenant_id)
    if busy:
        raise HTTPException(
            status_code=409,
            detail="A menu is already being read. Wait for it to finish, then upload the new one.",
        )

    job_id = await create_job(db, tenant_id, file.filename)
    start_job(job_id, tenant_id, file_bytes, file.filename)
    logger.info(f"[upload-menu-pdf] tenant={tenant_id} job={job_id} file={file.filename} bytes={len(file_bytes)}")
    return {"job_id": job_id, "status": "queued"}


@tenant_routes.get("/menu-uploads/latest")
async def latest_menu_upload(
    db=Depends(get_database),
    current_user: dict = Depends(require_owner),
):
    """The most recent menu upload, so a page reload picks up where it was."""
    tenant_id = current_user.get("active_tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="No active restaurant.")
    await mark_stale_jobs(db, tenant_id)
    doc = await db[MENU_JOBS].find_one({"tenant_id": tenant_id}, sort=[("created_at", -1)])
    return {"job": public(doc)}


@tenant_routes.get("/menu-uploads/{job_id}")
async def get_menu_upload(
    job_id: str,
    db=Depends(get_database),
    current_user: dict = Depends(require_owner),
):
    tenant_id = current_user.get("active_tenant_id")
    doc = await db[MENU_JOBS].find_one({"job_id": job_id, "tenant_id": tenant_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Upload not found.")
    return {"job": public(doc)}
