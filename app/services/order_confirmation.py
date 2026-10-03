"""
Customer confirmation for orders.

The agent never places an order on its own. It saves a draft, sends the
customer a summary with Confirm and Cancel buttons, and the order only goes to
the restaurant once the customer taps Confirm. This avoids duplicate and
unwanted orders.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

from core.whatsapp_utils import SendResult, resolve_tenant_whatsapp_credentials, send_buttons, send_text

logger = logging.getLogger(__name__)

AWAITING = "awaiting_customer"
CONFIRM_WINDOW = timedelta(minutes=30)
CONFIRM_PREFIX = "order_confirm:"
CANCEL_PREFIX = "order_cancel:"


def parse_button(button_id: str) -> Tuple[Optional[str], Optional[str]]:
    """'order_confirm:ORD-1' -> ('confirm', 'ORD-1'). Unknown ids -> (None, None)."""
    if button_id.startswith(CONFIRM_PREFIX):
        return "confirm", button_id[len(CONFIRM_PREFIX):]
    if button_id.startswith(CANCEL_PREFIX):
        return "cancel", button_id[len(CANCEL_PREFIX):]
    return None, None


def summary_text(order: Dict[str, Any]) -> str:
    currency = order.get("currency") or ""
    items = "\n".join(f"- {i['quantity']} x {i['name']}" for i in order.get("items", []))
    return (
        f"Please check your order, {order.get('customer_name') or 'there'}:\n"
        f"{items}\n"
        f"Delivery to: {order.get('delivery_address')}\n"
        f"Payment: {str(order.get('payment_method', 'cod')).upper()}\n"
        f"Total: {currency} {float(order.get('total_amount', 0)):.2f} (incl. delivery)\n\n"
        "Tap Confirm to place it, or Cancel."
    )


def _resolve(tenant: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    return resolve_tenant_whatsapp_credentials(tenant)


async def send_summary(db, tenant: Dict[str, Any], order: Dict[str, Any]) -> SendResult:
    token, phone_id = _resolve(tenant)
    return await send_buttons(
        to_phone=order["customer_phone"],
        body=summary_text(order),
        buttons=[
            {"id": f"{CONFIRM_PREFIX}{order['order_id']}", "title": "Confirm"},
            {"id": f"{CANCEL_PREFIX}{order['order_id']}", "title": "Cancel"},
        ],
        token=token,
        phone_number_id=phone_id,
    )


async def find_awaiting(db, tenant_id: str, customer_phone: str) -> Optional[Dict[str, Any]]:
    """A draft still waiting for this customer's answer, if one is recent enough."""
    return await db["orders"].find_one({
        "tenant_id": tenant_id,
        "customer_phone": customer_phone,
        "status": AWAITING,
        "created_at": {"$gte": datetime.now(timezone.utc) - CONFIRM_WINDOW},
    }, sort=[("created_at", -1)])


async def _reply(db, tenant: Dict[str, Any], customer_phone: str, text: str) -> None:
    from services.message_service import message_service

    token, phone_id = _resolve(tenant)
    await send_text(to_phone=customer_phone, text=text, token=token, phone_number_id=phone_id)
    conversation = await db["conversations"].find_one(
        {"tenant_id": tenant["tenant_id"], "customer_phone": customer_phone}, {"conversation_id": 1}
    )
    if conversation:
        await message_service.persist_outbound(
            conversation_id=conversation["conversation_id"],
            tenant_id=tenant["tenant_id"],
            content=text,
            sender="agent",
        )


async def handle_tap(db, tenant: Dict[str, Any], customer_phone: str, button_id: str) -> str:
    """Applies a Confirm or Cancel tap. Returns what happened, for logs."""
    from core.events import broadcast_order_update
    from services.order_service import initial_status_entry

    action, order_id = parse_button(button_id)
    if not action:
        return "unknown button"

    tenant_id = tenant["tenant_id"]
    order = await db["orders"].find_one({"tenant_id": tenant_id, "customer_phone": customer_phone, "order_id": order_id})
    if not order:
        await _reply(db, tenant, customer_phone, "Ye order mil nahi raha. Dobara order karein.")
        return "order not found"

    if order.get("status") != AWAITING:
        await _reply(db, tenant, customer_phone, f"Ye order pehle hi {order.get('status')} hai.")
        return f"already {order.get('status')}"

    now = datetime.now(timezone.utc)
    created = order.get("created_at")
    if created and created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    if created and now - created > CONFIRM_WINDOW:
        await db["orders"].update_one({"order_id": order_id}, {"$set": {"status": "expired", "updated_at": now}})
        await _reply(db, tenant, customer_phone, "Ye order expire ho gaya. Dobara order karein.")
        return "expired"

    if action == "cancel":
        entry = {"status": "cancelled", "at": now, "by": "customer", "by_user_id": None, "customer_notified": True}
        await db["orders"].update_one({"order_id": order_id}, {
            "$set": {"status": "cancelled", "cancellation_reason": "Customer cancelled before confirming", "updated_at": now},
            "$push": {"status_history": entry},
        })
        await _reply(db, tenant, customer_phone, "Thek hai, order cancel kar diya.")
        return "cancelled by customer"

    entry = {"status": "pending", "at": now, "by": "customer", "by_user_id": None, "customer_notified": True}
    await db["orders"].update_one({"order_id": order_id}, {
        "$set": {"status": "pending", "customer_confirmed_at": now, "updated_at": now},
        "$push": {"status_history": entry},
    })
    order["status"] = "pending"
    order.pop("_id", None)
    try:
        await broadcast_order_update(tenant_id=tenant_id, event_type="order.created", order_data=order)
    except Exception as e:
        logger.warning(f"Could not broadcast confirmed order {order_id}: {e}")
    await _reply(
        db, tenant, customer_phone,
        f"Order confirm ho gaya: {order_id}. {order.get('currency', '')} {float(order.get('total_amount', 0)):.2f}, "
        f"about {order.get('eta_minutes', 30)} minutes. Shukriya!",
    )
    return "confirmed"
