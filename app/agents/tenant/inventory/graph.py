import re
import logging
from typing import Dict, Any, Optional
from app.services.menu_parser import menu_parser_service
from app.agents.tenant.inventory.tools import (
    toggle_item_availability,
    save_ingested_menu,
    get_inventory_summary
)

logger = logging.getLogger(__name__)

async def process_owner_inventory_message(
    tenant_id: str,
    owner_phone: str,
    message_text: str,
    document_bytes: Optional[bytes] = None
) -> str:
    """Processes inbound WhatsApp communication from restaurant owner regarding menu/inventory."""
    
    # 1. Document / PDF Menu Ingestion
    if document_bytes:
        extracted_text = menu_parser_service.extract_text_from_pdf(document_bytes)
        parsed_menu = await menu_parser_service.parse_menu_content(extracted_text)
        ingest_res = await save_ingested_menu(tenant_id, parsed_menu)
        return (
            f"📄 *Menu Document Processed!*\n"
            f"✅ Ingested {ingest_res['items_added_or_updated']} items across {ingest_res['categories_added_or_updated']} categories.\n"
            "Your menu catalog is updated and live for customer WhatsApp ordering!"
        )

    clean_text = message_text.strip().lower()

    # 2. Check for inventory / stock summary request
    if any(k in clean_text for k in ["inventory", "stock list", "stock status", "items status"]):
        return await get_inventory_summary(tenant_id)

    # 3. Check for out of stock / 86 request
    out_of_stock_triggers = ["out of", "ran out of", "sold out", "no more", "86"]
    for trig in out_of_stock_triggers:
        if trig in clean_text:
            # Extract item name after trigger
            item_part = clean_text.split(trig)[-1].strip().strip("!.,")
            if item_part:
                res = await toggle_item_availability(tenant_id, item_part, is_available=False)
                return res["message"]

    # 4. Check for back in stock request
    in_stock_triggers = ["back in stock", "available again", "restocked", "have more"]
    for trig in in_stock_triggers:
        if trig in clean_text:
            item_part = clean_text.replace(trig, "").strip().strip("!.,")
            if item_part:
                res = await toggle_item_availability(tenant_id, item_part, is_available=True)
                return res["message"]

    # Default owner assistant response
    return (
        "👨‍🍳 *Restaurant Owner Assistant*\n"
        "Here is what you can do:\n"
        "• Drop a *PDF or Image Menu* directly in this chat to ingest/update your menu.\n"
        "• Reply *'Out of [item name]'* or *'Sold out [item name]'* to 86 an item.\n"
        "• Reply *'Back in stock [item name]'* to reactivate an item.\n"
        "• Reply *'Inventory'* to see live stock status."
    )
