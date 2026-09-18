import uuid
from typing import Optional, List
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.tenant import Tenant
from app.models.menu import MenuItem, MenuCategory
from app.agents.tenant.inventory.tools import toggle_item_availability, save_ingested_menu
from app.services.menu_parser import menu_parser_service

router = APIRouter(prefix="/menu", tags=["Menu & Inventory"])

class StockToggleRequest(BaseModel):
    tenant_id: str
    item_name: str
    is_available: bool

@router.get("/{tenant_id}")
async def get_menu(tenant_id: str):
    """Retrieve full menu catalog for a tenant."""
    async with AsyncSessionLocal() as db:
        stmt = (
            select(MenuItem)
            .where(MenuItem.tenant_id == uuid.UUID(tenant_id))
            .order_by(MenuItem.name)
        )
        res = await db.execute(stmt)
        items = res.scalars().all()
        return [
            {
                "id": str(it.id),
                "name": it.name,
                "description": it.description,
                "price": float(it.price),
                "is_available": it.is_available,
                "allergens": it.allergens
            }
            for it in items
        ]

@router.post("/toggle-stock")
async def toggle_stock(payload: StockToggleRequest):
    """Toggle 86 / availability of a menu item."""
    return await toggle_item_availability(
        tenant_id=payload.tenant_id,
        item_name=payload.item_name,
        is_available=payload.is_available
    )

@router.post("/upload-pdf")
async def upload_pdf_menu(
    tenant_id: str = Form(...),
    file: UploadFile = File(...)
):
    """Upload and parse a PDF menu directly from frontend or dashboard."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    content = await file.read()
    extracted_text = menu_parser_service.extract_text_from_pdf(content)
    parsed_menu = await menu_parser_service.parse_menu_content(extracted_text)
    save_result = await save_ingested_menu(tenant_id, parsed_menu)
    return {
        "status": "success",
        "filename": file.filename,
        "summary": save_result
    }
