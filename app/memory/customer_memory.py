from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from core.database import get_database


async def get_customer_profile(tenant_id: str, customer_phone: str) -> Optional[Dict[str, Any]]:
    """Retrieves long-term customer profile for a given restaurant tenant."""
    db = get_database()
    return await db["customer_profiles"].find_one({
        "tenant_id": tenant_id,
        "customer_phone": customer_phone
    })


async def update_customer_profile(
    tenant_id: str,
    customer_phone: str,
    name: Optional[str] = None,
    delivery_address: Optional[str] = None,
    notes: Optional[str] = None,
    order_amount: Optional[float] = None,
    favorite_items: Optional[List[str]] = None,
):
    """Updates or creates a long-term customer profile with preferences and history."""
    db = get_database()
    now = datetime.now(timezone.utc)

    update_fields: Dict[str, Any] = {
        "updated_at": now
    }
    if name:
        update_fields["name"] = name
    if notes:
        update_fields["notes"] = notes

    push_fields: Dict[str, Any] = {}
    if delivery_address:
        push_fields["delivery_addresses"] = delivery_address
    if favorite_items:
        push_fields["favorite_items"] = {"$each": favorite_items}

    inc_fields: Dict[str, Any] = {
        "total_orders": 1 if order_amount is not None else 0,
        "total_spent": float(order_amount) if order_amount is not None else 0.0,
    }

    update_doc: Dict[str, Any] = {
        "$set": update_fields,
        "$setOnInsert": {
            "tenant_id": tenant_id,
            "customer_phone": customer_phone,
            "created_at": now,
        },
        "$inc": inc_fields,
    }

    if push_fields:
        update_doc["$addToSet"] = push_fields

    await db["customer_profiles"].update_one(
        {"tenant_id": tenant_id, "customer_phone": customer_phone},
        update_doc,
        upsert=True
    )


async def format_customer_context(tenant_id: str, customer_phone: str) -> str:
    """Formats customer historical context for prompt injection."""
    profile = await get_customer_profile(tenant_id, customer_phone)
    if not profile:
        return "Customer Status: New Customer (no prior orders on record)."

    name = profile.get("name", "Unknown")
    total_orders = profile.get("total_orders", 0)
    total_spent = profile.get("total_spent", 0.0)
    addresses = profile.get("delivery_addresses", [])
    recent_addr = addresses[-1] if addresses else "None"
    favs = profile.get("favorite_items", [])
    notes = profile.get("notes", "None")

    return (
        f"Customer Context:\n"
        f"- Name: {name}\n"
        f"- Loyalty Tier: {'VIP / Frequent' if total_orders > 3 else 'Regular'}\n"
        f"- Total Previous Orders: {total_orders} (${total_spent:.2f} total spent)\n"
        f"- Known Delivery Address: {recent_addr}\n"
        f"- Favorite / Ordered Dishes: {', '.join(favs) if favs else 'None yet'}\n"
        f"- Notes / Preferences: {notes}"
    )
