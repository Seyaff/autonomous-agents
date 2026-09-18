import re
import uuid
import logging
from typing import Optional, List
import httpx
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.tenant import Tenant
from app.models.menu import MenuItem, MenuCategory
from app.services.kitchen_service import kitchen_service
from app.api.v1.ws_orders import ws_manager
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/onboarding", tags=["Luxury Onboarding"])

# Pydantic Schemas
class StartOnboardingRequest(BaseModel):
    name: str
    currency: Optional[str] = "PKR"

class UpdateIdentityRequest(BaseModel):
    name: Optional[str] = None
    cuisine: Optional[str] = None
    city: Optional[str] = None
    address: Optional[str] = None
    opening_hours: Optional[str] = None
    currency: Optional[str] = "PKR"
    kitchen_phone: Optional[str] = None

class MenuItemPayload(BaseModel):
    name: str
    category: str
    price: float
    is_available: bool = True
    description: Optional[str] = None

class IngestMenuRequest(BaseModel):
    items: List[MenuItemPayload]

class ConnectWhatsAppRequest(BaseModel):
    # Embedded Signup OAuth code from FB.login
    code: Optional[str] = None
    # Or direct/sandbox credentials
    phone_number_id: Optional[str] = None
    waba_id: Optional[str] = None
    access_token: Optional[str] = None
    display_phone_number: Optional[str] = None

class TestKitchenRequest(BaseModel):
    kitchen_phone: str

def generate_slug(name: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", name.lower()).strip("-")
    return cleaned or "restaurant"

@router.post("/start")
async def start_onboarding(payload: StartOnboardingRequest):
    """
    Step 0: Initializes a restaurant workspace draft.
    """
    async with AsyncSessionLocal() as db:
        base_slug = generate_slug(payload.name)
        slug = base_slug
        counter = 1
        while True:
            existing = (await db.execute(select(Tenant).where(Tenant.slug == slug))).scalar_one_or_none()
            if not existing:
                break
            slug = f"{base_slug}-{counter}"
            counter += 1

        tenant = Tenant(
            name=payload.name,
            slug=slug,
            currency=payload.currency or "PKR",
            onboarding_step="DRAFT",
            is_active=False
        )
        db.add(tenant)
        await db.commit()
        await db.refresh(tenant)

        return {
            "tenant_id": str(tenant.id),
            "slug": tenant.slug,
            "onboarding_step": tenant.onboarding_step,
            "message": "Tenant draft created successfully"
        }

@router.get("/{tenant_id}/status")
async def get_onboarding_status(tenant_id: str):
    """
    Returns the current onboarding step, checklist, and launchpad readiness score.
    """
    async with AsyncSessionLocal() as db:
        try:
            t_uuid = uuid.UUID(tenant_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid tenant UUID")

        res = await db.execute(select(Tenant).where(Tenant.id == t_uuid))
        tenant = res.scalar_one_or_none()
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")

        step_weights = {
            "DRAFT": 10,
            "IDENTITY_SAVED": 30,
            "MENU_INGESTED": 55,
            "WHATSAPP_CONNECTED": 80,
            "KITCHEN_VERIFIED": 95,
            "ACTIVE": 100,
        }
        progress = step_weights.get(tenant.onboarding_step, 10)

        whatsapp_connected = bool(tenant.phone_number_id)
        kitchen_verified = tenant.onboarding_step in ["KITCHEN_VERIFIED", "ACTIVE"]

        clean_phone = re.sub(r"\D", "", tenant.display_phone_number or tenant.owner_whatsapp_number or "")
        wa_link = f"https://wa.me/{clean_phone}?text=Assalam-o-Alaikum" if clean_phone else None

        return {
            "tenant_id": str(tenant.id),
            "slug": tenant.slug,
            "current_step": tenant.onboarding_step,
            "progress_percentage": progress,
            "identity": {
                "name": tenant.name,
                "cuisine": tenant.cuisine,
                "city": tenant.city,
                "address": tenant.address,
                "opening_hours": tenant.opening_hours,
                "currency": tenant.currency,
                "kitchen_phone": tenant.kitchen_whatsapp_number
            },
            "whatsapp_connected": whatsapp_connected,
            "kitchen_verified": kitchen_verified,
            "whatsapp_link": wa_link
        }

@router.patch("/{tenant_id}/identity")
async def update_identity(tenant_id: str, payload: UpdateIdentityRequest):
    """
    Step 1: Save restaurant identity, address, hours, and kitchen staff contact.
    """
    async with AsyncSessionLocal() as db:
        t_uuid = uuid.UUID(tenant_id)
        res = await db.execute(select(Tenant).where(Tenant.id == t_uuid))
        tenant = res.scalar_one_or_none()
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")

        if payload.name:
            tenant.name = payload.name
        if payload.cuisine:
            tenant.cuisine = payload.cuisine
        if payload.city:
            tenant.city = payload.city
        if payload.address:
            tenant.address = payload.address
        if payload.opening_hours:
            tenant.opening_hours = payload.opening_hours
        if payload.currency:
            tenant.currency = payload.currency
        if payload.kitchen_phone:
            tenant.kitchen_whatsapp_number = payload.kitchen_phone

        if tenant.onboarding_step == "DRAFT":
            tenant.onboarding_step = "IDENTITY_SAVED"

        await db.commit()
        await db.refresh(tenant)

        return {
            "status": "success",
            "current_step": tenant.onboarding_step,
            "tenant_id": str(tenant.id)
        }

@router.post("/{tenant_id}/menu")
async def ingest_menu(tenant_id: str, payload: IngestMenuRequest):
    """
    Step 2: Ingest structured dishes & categories.
    """
    async with AsyncSessionLocal() as db:
        t_uuid = uuid.UUID(tenant_id)
        res = await db.execute(select(Tenant).where(Tenant.id == t_uuid))
        tenant = res.scalar_one_or_none()
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")

        categories_map = {}
        # Fetch existing categories
        cat_res = await db.execute(select(MenuCategory).where(MenuCategory.tenant_id == t_uuid))
        for cat in cat_res.scalars().all():
            categories_map[cat.name.lower()] = cat.id

        created_items = []
        for item_data in payload.items:
            cat_name = item_data.category.strip()
            cat_key = cat_name.lower()
            if cat_key not in categories_map:
                new_cat = MenuCategory(
                    tenant_id=t_uuid,
                    name=cat_name,
                    display_order=len(categories_map) + 1
                )
                db.add(new_cat)
                await db.flush()
                categories_map[cat_key] = new_cat.id

            menu_item = MenuItem(
                tenant_id=t_uuid,
                category_id=categories_map[cat_key],
                name=item_data.name,
                description=item_data.description or "",
                price=item_data.price,
                is_available=item_data.is_available
            )
            db.add(menu_item)
            created_items.append(item_data.name)

        if tenant.onboarding_step in ["DRAFT", "IDENTITY_SAVED"]:
            tenant.onboarding_step = "MENU_INGESTED"

        await db.commit()
        return {
            "status": "success",
            "count": len(created_items),
            "current_step": tenant.onboarding_step
        }

@router.post("/{tenant_id}/whatsapp")
async def connect_whatsapp(tenant_id: str, payload: ConnectWhatsAppRequest):
    """
    Step 3: Meta Embedded Signup code exchange or manual sandbox credentials.
    """
    async with AsyncSessionLocal() as db:
        t_uuid = uuid.UUID(tenant_id)
        res = await db.execute(select(Tenant).where(Tenant.id == t_uuid))
        tenant = res.scalar_one_or_none()
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")

        # Case 1: OAuth Code from Meta Embedded Signup
        if payload.code:
            try:
                # Exchange code for system user access token
                token_url = "https://graph.facebook.com/v21.0/oauth/access_token"
                params = {
                    "client_id": settings.META_APP_ID if hasattr(settings, "META_APP_ID") else "",
                    "client_secret": settings.META_APP_SECRET if hasattr(settings, "META_APP_SECRET") else "",
                    "code": payload.code
                }
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.get(token_url, params=params)
                    if resp.status_code == 200:
                        token_data = resp.json()
                        tenant.meta_access_token = token_data.get("access_token")
                    else:
                        logger.warning(f"Meta token exchange returned {resp.status_code}: {resp.text}")
            except Exception as e:
                logger.error(f"Error exchanging Meta OAuth code: {e}")

        # Case 2: Direct or Sandbox parameters
        if payload.phone_number_id:
            tenant.phone_number_id = payload.phone_number_id
        if payload.waba_id:
            tenant.waba_id = payload.waba_id
        if payload.access_token:
            tenant.meta_access_token = payload.access_token
        if payload.display_phone_number:
            tenant.display_phone_number = payload.display_phone_number

        # Update onboarding step
        tenant.onboarding_step = "WHATSAPP_CONNECTED"
        await db.commit()
        await db.refresh(tenant)

        # Attempt to register webhook subscription if waba_id is present
        if tenant.waba_id and tenant.meta_access_token:
            try:
                sub_url = f"https://graph.facebook.com/v21.0/{tenant.waba_id}/subscribed_apps"
                headers = {"Authorization": f"Bearer {tenant.meta_access_token}"}
                async with httpx.AsyncClient(timeout=10.0) as client:
                    await client.post(sub_url, headers=headers)
            except Exception as e:
                logger.warning(f"Could not auto-subscribe WABA to webhook: {e}")

        return {
            "status": "success",
            "phone_number_id": tenant.phone_number_id,
            "current_step": tenant.onboarding_step
        }

@router.post("/{tenant_id}/test-kitchen")
async def send_test_kitchen_ticket(tenant_id: str, payload: TestKitchenRequest):
    """
    Step 4: Dispatches a live test ticket to kitchen staff phone and KDS WebSocket.
    """
    async with AsyncSessionLocal() as db:
        t_uuid = uuid.UUID(tenant_id)
        res = await db.execute(select(Tenant).where(Tenant.id == t_uuid))
        tenant = res.scalar_one_or_none()
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")

        tenant.kitchen_whatsapp_number = payload.kitchen_phone
        ticket_text = kitchen_service.format_kitchen_ticket(
            order_number="TEST-01",
            order_type="delivery",
            delivery_address="Ring Road, Kohat (Test Dispatch)",
            items=[
                {"name": "Shinwari Mutton Karahi (Full)", "quantity": 1, "notes": "Medium spice, test ticket"},
                {"name": "Roghani Naan", "quantity": 2, "notes": "Fresh from tandoor"},
                {"name": "Peshawari Kahwa", "quantity": 1, "notes": "Complimentary"}
            ],
            total_amount=2560.0,
            payment_method="TEST COD",
            customer_notes="Please confirm receipt of this test order."
        )

        sent = await kitchen_service.dispatch_ticket_to_kitchen(
            kitchen_phone=payload.kitchen_phone,
            ticket_text=ticket_text,
            phone_number_id=tenant.phone_number_id,
            access_token=tenant.meta_access_token or settings.META_ACCESS_TOKEN
        )

        # Broadcast test event to WebSocket KDS
        await ws_manager.broadcast_order_event(
            tenant_id=tenant_id,
            event_type="ORDER_CREATED",
            data={
                "order_number": "TEST-01",
                "status": "confirmed",
                "total_amount": 2560.0,
                "is_test": True
            }
        )

        tenant.onboarding_step = "KITCHEN_VERIFIED"
        await db.commit()

        return {
            "status": "success",
            "whatsapp_sent": sent,
            "current_step": tenant.onboarding_step,
            "message": f"Test ticket dispatched to kitchen staff at {payload.kitchen_phone}"
        }

@router.post("/{tenant_id}/complete")
async def complete_onboarding(tenant_id: str):
    """
    Step 5: Activates the restaurant workspace and outputs public wa.me ordering link.
    """
    async with AsyncSessionLocal() as db:
        t_uuid = uuid.UUID(tenant_id)
        res = await db.execute(select(Tenant).where(Tenant.id == t_uuid))
        tenant = res.scalar_one_or_none()
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")

        tenant.is_active = True
        tenant.onboarding_step = "ACTIVE"
        await db.commit()

        clean_phone = re.sub(r"\D", "", tenant.display_phone_number or tenant.owner_whatsapp_number or "923417268523")
        whatsapp_link = f"https://wa.me/{clean_phone}?text=Assalam-o-Alaikum"

        return {
            "status": "active",
            "tenant_id": str(tenant.id),
            "slug": tenant.slug,
            "whatsapp_link": whatsapp_link,
            "message": "Restaurant is now live! Customers can start ordering immediately."
        }
