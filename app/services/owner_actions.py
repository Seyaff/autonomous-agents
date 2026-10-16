"""
Things the owner does to orders and chats. The dashboard routes and the owner's agent both call these,
so a change made by typing goes through the same checks as one made by clicking.

Errors are raised as ActionError with a message the owner can read and the HTTP status a route should use.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from core.events import broadcast_order_update
from services.alerts import raise_alert
from services.channels import channel_of, send_text_to
from services.conversation_state import broadcast_conversation_updated
from services.order_service import ORDER_STATUSES, customer_in_service_window, is_valid_transition, notify_customer_status


class ActionError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


async def change_order_status(
    db,
    tenant: Dict[str, Any],
    order_id: str,
    new_status: str,
    user_id: Optional[str],
    notes: Optional[str] = None,
) -> Tuple[Dict[str, Any], bool]:
    """Moves an order to a new status, tells the customer when the channel allows it, and records who did it.
    Returns the updated order and whether the customer was told."""
    tenant_id = tenant["tenant_id"]
    order = await db["orders"].find_one({"order_id": order_id, "tenant_id": tenant_id})
    if not order:
        raise ActionError("Order not found", 404)

    new_status = (new_status or "").lower()
    if new_status not in ORDER_STATUSES:
        raise ActionError(f"Invalid status. Must be one of: {list(ORDER_STATUSES)}", 400)

    current_status = order.get("status", "pending")
    if not is_valid_transition(current_status, new_status):
        raise ActionError(f"Cannot move order from '{current_status}' to '{new_status}'.", 409)

    now = datetime.now(timezone.utc)
    customer_notified = await notify_customer_status(db, tenant, order, new_status)

    history_entry = {
        "status": new_status,
        "at": now,
        "by": "owner",
        "by_user_id": user_id,
        "customer_notified": customer_notified,
    }
    update_doc: Dict[str, Any] = {"status": new_status, "updated_at": now}
    if notes:
        update_doc["admin_notes"] = notes

    await db["orders"].update_one(
        {"order_id": order_id, "tenant_id": tenant_id},
        {"$set": update_doc, "$push": {"status_history": history_entry}},
    )

    order.update(update_doc)
    order.setdefault("status_history", []).append(history_entry)
    order.pop("_id", None)

    await broadcast_order_update(tenant_id=tenant_id, event_type="order.updated", order_data=order)
    return order, customer_notified


async def set_handover(tenant_id: str, conversation_id: str, handled_by: str, user_id: Optional[str]) -> Dict[str, Any]:
    """Gives the chat to the owner ("owner") or back to the agent ("agent"), and tells open dashboards."""
    from repositories.inbox_repo import inbox_repo

    conversation = await inbox_repo.set_handover(conversation_id, tenant_id, handled_by, user_id)
    await broadcast_conversation_updated(tenant_id, conversation)
    return conversation


async def resolve_escalation(tenant_id: str, conversation_id: str, user_id: Optional[str]) -> Dict[str, Any]:
    """Clears the "needs you" flag without changing who is handling the chat."""
    from repositories.inbox_repo import inbox_repo

    conversation = await inbox_repo.resolve_escalation(conversation_id, tenant_id, user_id)
    await broadcast_conversation_updated(tenant_id, conversation)
    return conversation


def window_closed_message(contact: str) -> str:
    if channel_of(contact) == "instagram":
        return "It's been more than 24 hours since this customer wrote. Instagram only allows a reply after they write again."
    return "It's been more than 24 hours since this customer wrote. WhatsApp only allows a template now."


async def owner_reply(
    db,
    tenant: Dict[str, Any],
    conversation: Dict[str, Any],
    content: str,
    user_id: Optional[str],
    message_type: str = "text",
) -> Tuple[bool, Any]:
    """Sends the owner's own message to the customer. Replying is taking over: if the agent was still handling
    the chat, it is switched to the owner first so the agent doesn't answer on top of them.
    Returns whether it was sent, and the saved message."""
    from services.message_service import message_service

    tenant_id = tenant["tenant_id"]
    conversation_id = conversation["conversation_id"]
    contact = conversation["customer_phone"]

    if not await customer_in_service_window(db, tenant_id, contact):
        raise ActionError(window_closed_message(contact), 409)

    if conversation.get("handled_by") != "owner":
        await set_handover(tenant_id, conversation_id, "owner", user_id)

    message = await message_service.persist_outbound(
        conversation_id=conversation_id,
        tenant_id=tenant_id,
        content=content,
        message_type=message_type,
        sender="human",
    )

    result = await send_text_to(tenant, contact, content, db)
    sent = result.ok

    if message:
        await message_service.update_outbound_status(
            message_id=message.message_id,
            wamid=result.message_id or "",
            status="sent" if sent else "failed",
        )
    if not sent:
        await raise_alert(
            db,
            tenant_id,
            kind="owner_message_not_sent",
            title="Your reply wasn't delivered",
            detail=f"{contact}: {result.error_message or 'The message was not accepted.'}",
            severity="critical" if result.auth_error else "warning",
            ref={"conversation_id": conversation_id},
        )
    return sent, message
