import logging
from typing import Optional, List
from app.services.whatsapp_service import whatsapp_service
from app.config import settings

logger = logging.getLogger(__name__)

class KitchenService:
    @staticmethod
    def format_kitchen_ticket(
        order_number: str,
        order_type: str,
        delivery_address: Optional[str],
        items: List[dict],
        total_amount: float,
        payment_method: str = "COD",
        customer_notes: Optional[str] = None,
        created_time_str: Optional[str] = None
    ) -> str:
        """
        Formats a monospaced, bold WhatsApp order ticket for kitchen chefs.
        """
        time_display = created_time_str or "Just now"
        address_line = f"📍 Address: {delivery_address}" if delivery_address else "📍 Dine-in / Pickup"
        
        lines = [
            f"🔔 *KITCHEN TICKET #{order_number}*",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            f"⏰ Time: {time_display} | Type: {order_type.upper()}",
            address_line,
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "*ITEMS TO PREPARE:*"
        ]
        
        for item in items:
            name = item.get("name") or item.get("item_name", "Dish")
            qty = item.get("quantity", 1)
            notes = item.get("special_instructions") or item.get("notes")
            lines.append(f"• *{qty}x {name}*")
            if notes:
                lines.append(f"  ↳ Note: _{notes}_")
                
        if customer_notes:
            lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            lines.append(f"📝 Customer Note: _{customer_notes}_")

        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append(f"💰 Total: *Rs. {total_amount:,.0f}* ({payment_method.upper()})")
        lines.append("Reply *Ready* when kitchen finishes packing!")
        
        return "\n".join(lines)

    async def dispatch_ticket_to_kitchen(
        self,
        kitchen_phone: str,
        ticket_text: str,
        phone_number_id: Optional[str] = None,
        access_token: Optional[str] = None
    ) -> bool:
        """
        Sends formatted order ticket to kitchen staff WhatsApp number.
        """
        if not kitchen_phone:
            logger.warning("No kitchen phone configured for ticket dispatch.")
            return False

        try:
            res = await whatsapp_service.send_text_message(
                to_phone=kitchen_phone,
                text=ticket_text,
                phone_number_id=phone_number_id,
                access_token=access_token or settings.META_ACCESS_TOKEN
            )
            logger.info(f"Kitchen ticket sent to {kitchen_phone}: {res}")
            return True
        except Exception as e:
            logger.error(f"Failed to send ticket to kitchen phone {kitchen_phone}: {e}")
            return False

kitchen_service = KitchenService()
