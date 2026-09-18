import uuid
import logging
from typing import List, Dict, Any, Optional
from sqlalchemy import select, update
from app.core.database import AsyncSessionLocal
from app.models.menu import MenuItem, MenuCategory
from app.models.tenant import Tenant

logger = logging.getLogger(__name__)

async def toggle_item_availability(
    tenant_id: str,
    item_name: str,
    is_available: bool
) -> Dict[str, Any]:
    """Toggle stock availability (86 status) for a menu item."""
    async with AsyncSessionLocal() as db:
        stmt = (
            select(MenuItem)
            .where(MenuItem.tenant_id == uuid.UUID(tenant_id))
            .where(MenuItem.name.ilike(f"%{item_name}%"))
        )
        res = await db.execute(stmt)
        item = res.scalars().first()

        if not item:
            return {
                "success": False,
                "message": f"Could not find menu item matching '{item_name}'."
            }

        item.is_available = is_available
        await db.commit()
        status_str = "in stock" if is_available else "OUT OF STOCK (86'd)"
        return {
            "success": True,
            "item_name": item.name,
            "is_available": is_available,
            "message": f"Updated *{item.name}* to: *{status_str}*."
        }

async def save_ingested_menu(
    tenant_id: str,
    parsed_categories: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Persist parsed menu categories and items into the restaurant's catalog."""
    total_items = 0
    total_categories = 0

    async with AsyncSessionLocal() as db:
        t_uuid = uuid.UUID(tenant_id)
        for cat_data in parsed_categories:
            cat_name = cat_data.get("category_name", "General")
            
            # Check if category exists
            cat_stmt = (
                select(MenuCategory)
                .where(MenuCategory.tenant_id == t_uuid)
                .where(MenuCategory.name.ilike(cat_name))
            )
            res = await db.execute(cat_stmt)
            category = res.scalar_one_or_none()
            if not category:
                category = MenuCategory(tenant_id=t_uuid, name=cat_name)
                db.add(category)
                await db.flush()
                total_categories += 1

            for item_data in cat_data.get("items", []):
                item_name = item_data.get("name", "Untitled")
                price = float(item_data.get("price", 0.0))
                desc = item_data.get("description", "")
                allergens = item_data.get("allergens", [])

                # Check if item exists
                item_stmt = (
                    select(MenuItem)
                    .where(MenuItem.tenant_id == t_uuid)
                    .where(MenuItem.name.ilike(item_name))
                )
                i_res = await db.execute(item_stmt)
                existing_item = i_res.scalar_one_or_none()

                if existing_item:
                    existing_item.price = price
                    existing_item.description = desc
                    existing_item.is_available = True
                else:
                    new_item = MenuItem(
                        tenant_id=t_uuid,
                        category_id=category.id,
                        name=item_name,
                        description=desc,
                        price=price,
                        allergens=allergens,
                        is_available=True
                    )
                    db.add(new_item)
                    total_items += 1

        await db.commit()

    return {
        "status": "success",
        "categories_added_or_updated": total_categories,
        "items_added_or_updated": total_items
    }

async def get_inventory_summary(tenant_id: str) -> str:
    """Retrieve full inventory status for restaurant owner review."""
    async with AsyncSessionLocal() as db:
        stmt = (
            select(MenuItem)
            .where(MenuItem.tenant_id == uuid.UUID(tenant_id))
            .order_by(MenuItem.name)
        )
        res = await db.execute(stmt)
        items = res.scalars().all()
        if not items:
            return "No menu items found in catalog."

        lines = ["📦 *Current Restaurant Inventory:*"]
        for it in items:
            status = "✅ In Stock" if it.is_available else "❌ Out of Stock"
            lines.append(f"• *{it.name}* (${it.price:.2f}) — {status}")
        return "\n".join(lines)
