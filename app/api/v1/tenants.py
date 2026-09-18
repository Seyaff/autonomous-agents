import uuid
from typing import Optional, List
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.tenant import Tenant

router = APIRouter(prefix="/tenants", tags=["Tenants"])

class CreateTenantRequest(BaseModel):
    name: str
    slug: str
    owner_whatsapp_number: Optional[str] = None
    phone_number_id: Optional[str] = None
    display_phone_number: Optional[str] = None
    address: Optional[str] = None
    currency: str = "USD"

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_tenant(payload: CreateTenantRequest):
    """Register a new restaurant tenant."""
    async with AsyncSessionLocal() as db:
        # Check slug uniqueness
        existing = await db.execute(select(Tenant).where(Tenant.slug == payload.slug))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="A restaurant with this slug already exists.")

        tenant = Tenant(
            name=payload.name,
            slug=payload.slug,
            owner_whatsapp_number=payload.owner_whatsapp_number,
            phone_number_id=payload.phone_number_id,
            display_phone_number=payload.display_phone_number,
            address=payload.address,
            currency=payload.currency,
            is_active=True
        )
        db.add(tenant)
        await db.commit()
        await db.refresh(tenant)
        return {
            "id": str(tenant.id),
            "name": tenant.name,
            "slug": tenant.slug,
            "owner_whatsapp_number": tenant.owner_whatsapp_number,
            "phone_number_id": tenant.phone_number_id
        }

@router.get("")
async def list_tenants():
    """List all registered restaurants."""
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(Tenant))
        tenants = res.scalars().all()
        return [
            {
                "id": str(t.id),
                "name": t.name,
                "slug": t.slug,
                "phone_number_id": t.phone_number_id,
                "owner_whatsapp_number": t.owner_whatsapp_number,
                "is_active": t.is_active
            }
            for t in tenants
        ]
