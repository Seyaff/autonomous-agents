import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Literal
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from pymongo.errors import PyMongoError

from core.database import get_database
from repositories.inbox_repo import inbox_repo
from services.conversation_state import broadcast_conversation_updated
from services.alerts import raise_alert
from services.order_service import BOOKING_FORMAT, compute_totals, initial_status_entry, parse_booking_time
from services.order_confirmation import AWAITING, find_awaiting, send_summary
from services.availability import catalog_prices, is_sold_out, normalize, sold_out_names
from services.menu_view import menu_text
from core.setup_state import ORDER_TYPE_LABELS, hours_status
from core.events import broadcast_order_update

logger = logging.getLogger(__name__)


from services.knowledge_ingestion import search_tenant_knowledge

@tool
async def search_uploaded_documents(query: str, config: RunnableConfig) -> str:
    """Searches the business's uploaded documents: menus, price lists, service lists, offers, policies and FAQs.
    ALWAYS call this first before answering questions about offers, policies, how things work, or details
    that aren't in the catalog.
    """
    configurable = config.get("configurable", {})
    tenant_id = configurable.get("tenant_id")
    if not tenant_id:
        return "System notice: Business tenant ID missing from context. Cannot search documents."

    return await search_tenant_knowledge(query=query, tenant_id=tenant_id, top_k=4)


@tool
async def get_catalog(category: Optional[str] = None, config: RunnableConfig = None) -> str:
    """Returns what the business sells (products, services or dishes), grouped by category, with prices.
    Use it for any question about what's available or what it costs. Pass a category name to narrow it down.
    """
    configurable = (config or {}).get("configurable", {})
    tenant_id = configurable.get("tenant_id")
    if not tenant_id:
        return "System notice: Business tenant ID missing from context. Cannot read the catalog."
    db = get_database()
    tenant = await db["tenants"].find_one({"tenant_id": tenant_id}) or {"tenant_id": tenant_id}
    text = await menu_text(db, tenant, category)
    if not text:
        return "The catalog isn't set up yet. Use search_uploaded_documents for details."
    return text


def price_items(items: List[Dict[str, Any]], catalog: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Normalizes the model's items. An item that is in the owner's catalog takes the catalog's name and price."""
    formatted = []
    for item in items:
        name = str(item.get("name", "Unknown Item")).strip()
        qty = max(1, int(item.get("quantity", 1)))
        price = float(item.get("price", 0.0))
        known = catalog.get(normalize(name))
        if known and isinstance(known.get("price"), (int, float)):
            name, price = known["name"], float(known["price"])
        formatted.append({"name": name, "quantity": qty, "price": price, "notes": item.get("notes")})
    return formatted


@tool
async def create_order_tool(
    items: List[Dict[str, Any]],
    order_type: Literal["delivery", "takeaway", "dine_in", "booking"] = "delivery",
    delivery_address: Optional[str] = None,
    scheduled_for: Optional[str] = None,
    payment_method: str = "cod",
    customer_notes: Optional[str] = None,
    customer_name: Optional[str] = None,
    contact_phone: Optional[str] = None,
    config: RunnableConfig = None
) -> str:
    """Saves a customer's order or booking as a draft and sends them a summary to confirm.

    Args:
        items: What the customer wants. Each dict MUST contain 'name', 'quantity', and 'price'.
               Example: [{"name": "Haircut", "quantity": 1, "price": 1500}]
               Prices of catalog items are taken from the catalog. The total is calculated by the system.
        order_type: 'delivery' (sent to the customer), 'takeaway' (customer picks it up),
               'dine_in' (served at the business's own place), or 'booking' (an appointment at a set date and time).
        delivery_address: Required for delivery.
        scheduled_for: Required for a booking: "YYYY-MM-DD HH:MM" in the business's local time.
        payment_method: Payment method chosen by customer ('cod', 'card', 'cash'). Default is 'cod'.
        customer_notes: Optional special instructions.
        customer_name: The customer's name. Required.
        contact_phone: A phone number the customer gave. Needed for delivery when they wrote on Instagram.
    """
    configurable = config.get("configurable", {}) if config else {}
    tenant_id = configurable.get("tenant_id", "default_tenant")
    customer_phone = configurable.get("customer_phone", "unknown_customer")

    try:
        db = get_database()
        order_id = f"ORD-{uuid.uuid4().hex[:8].upper()}"

        tenant_doc = await db["tenants"].find_one({"tenant_id": tenant_id}) or {"tenant_id": tenant_id}
        currency = tenant_doc.get("currency") or "USD"
        hours = tenant_doc.get("operating_hours") or []
        tz_name = tenant_doc.get("timezone") or "UTC"

        offered = tenant_doc.get("order_types") or []
        if offered and order_type not in offered:
            return (
                f"This business doesn't take {ORDER_TYPE_LABELS.get(order_type, order_type)} orders. "
                f"It takes: {', '.join(ORDER_TYPE_LABELS.get(t, t) for t in offered)}. Ask the customer which they want."
            )

        scheduled_at = None
        if order_type == "booking":
            if not scheduled_for:
                return "Ask the customer for the date and time of the booking first."
            try:
                scheduled_at = parse_booking_time(scheduled_for, tz_name)
            except ValueError as e:
                return str(e)
            if scheduled_at <= datetime.now(timezone.utc):
                return "That booking time has already passed. Ask the customer for a time in the future."
            if not hours_status(hours, tz_name, scheduled_at)["open_now"]:
                return (
                    f"The business is closed at {scheduled_at.strftime(BOOKING_FORMAT)}. "
                    "Tell the customer the opening hours and ask for another time."
                )
        else:
            # Hard rule, not just prompt guidance: nothing for right now while the business is shut.
            open_state = hours_status(hours, tz_name)
            if not open_state["open_now"]:
                opens = open_state.get("opens_next") or "later"
                return (
                    f"The business is closed right now. Next opening: {opens}. "
                    "Don't place the order. Tell the customer when we open."
                )

        if order_type == "delivery" and not (delivery_address or "").strip():
            return "Ask the customer for the delivery address first."
        if configurable.get("channel") == "instagram" and order_type == "delivery" and not (contact_phone or "").strip():
            return "Ask the customer for a phone number for the delivery first. You don't have it on Instagram."

        formatted_items = price_items(items, await catalog_prices(db, tenant_id))
        if not formatted_items:
            return "There's nothing in the order. Ask the customer what they want."

        # Unavailable items are refused here too, not only in the prompt.
        sold_out = await sold_out_names(db, tenant_doc)
        blocked = [i["name"] for i in formatted_items if is_sold_out(i["name"], sold_out)]
        if blocked:
            return (
                f"Not available today: {', '.join(blocked)}. Don't place the order with them. "
                "Tell the customer and ask them to pick something else."
            )

        subtotal, delivery_fee, total_amount, eta_minutes = compute_totals(formatted_items, tenant_doc, order_type)

        minimum = float(tenant_doc.get("min_order_amount") or 0)
        if minimum and subtotal < minimum:
            return (
                f"Order is below the minimum of {currency} {minimum:.0f} "
                f"(subtotal {currency} {subtotal:.2f}). Ask the customer to add items."
            )

        if not (customer_name or "").strip():
            return "Ask the customer for their name first. Don't place the order until you have it."

        if not configurable.get("test_mode"):
            waiting = await find_awaiting(db, tenant_id, customer_phone)
            if waiting:
                # Don't stack a second order on top of one the customer hasn't answered yet.
                await send_summary(db, tenant_doc, waiting)
                return (
                    "An order is already waiting for the customer's answer. The summary was sent again. "
                    "Don't place another one; wait for them to tap Confirm."
                )

        if configurable.get("test_mode"):
            # Test chat: show what would happen, change nothing.
            test_items = ", ".join(f"{i['quantity']}x {i['name']}" for i in formatted_items)
            when = f"\nBooked for: {scheduled_at.strftime(BOOKING_FORMAT)}" if scheduled_at else ""
            return (
                f"Order placed. Reference ID: TEST-{uuid.uuid4().hex[:6].upper()} (test chat, not saved).\n"
                f"Type: {ORDER_TYPE_LABELS.get(order_type, order_type)}{when}\n"
                f"Items: {test_items}\n"
                f"Subtotal: {currency} {subtotal:.2f}, Delivery: {currency} {delivery_fee:.2f}\n"
                f"Total Amount: {currency} {total_amount:.2f}"
            )
        now = datetime.now(timezone.utc)
        order_document = {
            "order_id": order_id,
            "tenant_id": tenant_id,
            "customer_phone": customer_phone,
            "customer_name": customer_name.strip(),
            "conversation_id": f"conv_{tenant_id}_{customer_phone}",
            "source": "ai_agent",
            "order_type": order_type,
            "delivery_address": delivery_address.strip() if order_type == "delivery" and delivery_address else None,
            "scheduled_for": scheduled_at.astimezone(timezone.utc) if scheduled_at else None,
            "scheduled_for_local": scheduled_at.strftime(BOOKING_FORMAT) if scheduled_at else None,
            "items": formatted_items,
            "currency": currency,
            "subtotal": subtotal,
            "delivery_fee": delivery_fee,
            "total_amount": total_amount,
            "eta_minutes": eta_minutes,
            "payment_method": payment_method,
            "customer_notes": customer_notes,
            "contact_phone": (contact_phone or "").strip() or None,
            "channel": configurable.get("channel") or "whatsapp",
            # Not placed until the customer taps Confirm.
            "status": AWAITING,
            "status_history": [initial_status_entry(now, by="agent")],
            "created_at": now,
            "updated_at": now,
        }

        result = await db["orders"].insert_one(order_document)
        if not result.inserted_id:
            return "Database error: Could not save the order draft."

        sent = await send_summary(db, tenant_doc, order_document)
        if not sent.ok:
            logger.warning(f"Order summary for {order_id} could not be sent: {sent.error_message}")
            await db["orders"].update_one({"order_id": order_id}, {"$set": {"status": "cancelled", "cancellation_reason": "Summary not delivered"}})
            return "The order summary could not be sent to the customer. Ask them to send their order again."

        return (
            f"Summary sent to the customer with Confirm and Cancel buttons (order {order_id}). "
            "The order is NOT placed yet. Do not say it is placed or confirmed. "
            "Ask the customer to tap Confirm, and say the business will get it once they do."
        )

    except PyMongoError as e:
        logger.error(f"PyMongo error in create_order_tool: {e}")
        await _alert_order_failed(tenant_id, customer_phone, str(e))
        return f"Database error creating order: {str(e)}"
    except Exception as e:
        logger.error(f"Unexpected error in create_order_tool: {e}")
        await _alert_order_failed(tenant_id, customer_phone, str(e))
        return f"Failed to place order: {str(e)}"


async def _alert_order_failed(tenant_id: str, customer_phone: str, reason: str) -> None:
    """A customer tried to order and the order was not saved. The owner needs to know."""
    if tenant_id == "default_tenant" or not customer_phone or customer_phone == "unknown_customer":
        return
    await raise_alert(
        get_database(),
        tenant_id,
        kind="order_failed",
        title=f"An order from {customer_phone} was not saved",
        detail=f"The customer was told it failed, so they may call. ({reason[:160]})",
        severity="critical",
        ref={"customer_phone": customer_phone},
    )


@tool
async def get_order_status_tool(
    order_id: Optional[str] = None,
    config: RunnableConfig = None
) -> str:
    """Checks the status of the customer's current or recent orders and bookings.

    Args:
        order_id: Specific Order ID (e.g. 'ORD-A1B2C3D4'). If omitted, retrieves customer's latest order.
    """
    configurable = config.get("configurable", {}) if config else {}
    tenant_id = configurable.get("tenant_id")
    customer_phone = configurable.get("customer_phone")

    try:
        db = get_database()
        query: Dict[str, Any] = {"tenant_id": tenant_id}
        if order_id:
            query["order_id"] = order_id.strip()
        elif customer_phone:
            query["customer_phone"] = customer_phone
        else:
            return "Cannot retrieve order without customer phone or order reference ID."

        order = await db["orders"].find_one(query, sort=[("created_at", -1)])
        if not order:
            return f"No matching order found for {order_id or customer_phone}."

        ref = order.get("order_id")
        status = order.get("status", "pending").upper()
        total = order.get("total_amount", 0.0)
        items = order.get("items", [])
        items_summary = ", ".join([f"{i.get('quantity', 1)}x {i.get('name', 'item')}" for i in items])
        kind = order.get("order_type") or "delivery"
        if kind == "booking":
            where = f"- Booked for: {order.get('scheduled_for_local') or 'not set'}"
        elif kind == "delivery":
            where = f"- Delivery To: {order.get('delivery_address') or 'not set'}"
        else:
            where = f"- Type: {ORDER_TYPE_LABELS.get(kind, kind)}"
        created = order.get("created_at")
        time_str = created.strftime("%Y-%m-%d %H:%M UTC") if isinstance(created, datetime) else "Recently"

        return (
            f"Order Details for {ref}:\n"
            f"- Status: {status}\n"
            f"- Placed At: {time_str}\n"
            f"- Items: {items_summary}\n"
            f"- Total: {order.get('currency', 'USD')} {total:.2f}\n"
            f"{where}"
        )

    except Exception as e:
        logger.error(f"Error querying order status: {e}")
        return f"Could not fetch order status: {str(e)}"


@tool
async def update_order_tool(
    order_id: str,
    new_delivery_address: Optional[str] = None,
    additional_notes: Optional[str] = None,
    config: RunnableConfig = None
) -> str:
    """Updates an existing order's delivery address or special instructions.
    Orders can only be modified if they are still in 'pending' or 'accepted' status.

    Args:
        order_id: The Reference ID of the order to modify.
        new_delivery_address: Optional updated delivery location.
        additional_notes: Optional new instructions or notes.
    """
    configurable = config.get("configurable", {}) if config else {}
    tenant_id = configurable.get("tenant_id")

    try:
        db = get_database()
        order = await db["orders"].find_one({"order_id": order_id.strip(), "tenant_id": tenant_id})
        if not order:
            return f"Order '{order_id}' not found."

        current_status = order.get("status", "pending")
        if current_status not in ["pending", "accepted"]:
            return f"Order '{order_id}' cannot be modified because its status is already '{current_status.upper()}'."

        if configurable.get("test_mode"):
            return f"TEST: order '{order_id}' would be updated. Nothing was changed."

        update_fields: Dict[str, Any] = {"updated_at": datetime.now(timezone.utc)}
        if new_delivery_address:
            update_fields["delivery_address"] = new_delivery_address
        if additional_notes:
            update_fields["customer_notes"] = additional_notes

        await db["orders"].update_one({"order_id": order_id.strip()}, {"$set": update_fields})

        order.update(update_fields)
        if "_id" in order:
            order["_id"] = str(order["_id"])

        await broadcast_order_update(
            tenant_id=tenant_id,
            event_type="order.updated",
            order_data=order
        )

        return f"Order '{order_id}' has been updated successfully."

    except Exception as e:
        logger.error(f"Error updating order: {e}")
        return f"Could not update order: {str(e)}"


@tool
async def cancel_order_tool(
    order_id: str,
    reason: Optional[str] = None,
    config: RunnableConfig = None
) -> str:
    """Cancels a customer order or booking if it isn't already on its way or done.

    Args:
        order_id: The Reference ID of the order to cancel.
        reason: Optional reason for cancellation.
    """
    configurable = config.get("configurable", {}) if config else {}
    tenant_id = configurable.get("tenant_id")

    try:
        db = get_database()
        order = await db["orders"].find_one({"order_id": order_id.strip(), "tenant_id": tenant_id})
        if not order:
            return f"Order '{order_id}' not found."

        current_status = order.get("status", "pending")
        if current_status in ["out_for_delivery", "delivered"]:
            return f"Cannot cancel order '{order_id}'. It is already {current_status.upper()}."

        if current_status == "cancelled":
            return f"Order '{order_id}' is already cancelled."

        if configurable.get("test_mode"):
            return f"TEST: order '{order_id}' would be cancelled. Nothing was changed."

        update_fields = {
            "status": "cancelled",
            "cancellation_reason": reason or "Customer requested cancellation",
            "updated_at": datetime.now(timezone.utc)
        }
        await db["orders"].update_one({"order_id": order_id.strip()}, {"$set": update_fields})

        order.update(update_fields)
        if "_id" in order:
            order["_id"] = str(order["_id"])

        await broadcast_order_update(
            tenant_id=tenant_id,
            event_type="order.cancelled",
            order_data=order
        )

        return f"Order '{order_id}' has been cancelled successfully."

    except Exception as e:
        logger.error(f"Error cancelling order: {e}")
        return f"Could not cancel order: {str(e)}"

@tool
async def escalate_to_owner(
    reason: Literal["refund", "complaint", "human_requested", "agent_failed", "other"],
    summary: str,
    config: RunnableConfig = None,
) -> str:
    """Hands this customer's chat to the business owner. Use it for refund
    requests, complaints, requests to speak to a person, and anything you
    cannot resolve from the catalog, documents or order tools. After calling it,
    tell the customer you've passed this on and a person will follow up.

    Args:
        reason: Why it needs a person: refund, complaint, human_requested, agent_failed, other.
        summary: One line for the owner, e.g. "Wants refund for a damaged item, ORD-6A21".
    """
    configurable = config.get("configurable", {}) if config else {}
    tenant_id = configurable.get("tenant_id")
    customer_phone = configurable.get("customer_phone")
    if not tenant_id or not customer_phone:
        return "Could not escalate: missing conversation context."

    if configurable.get("test_mode"):
        return "Escalated to the owner. Tell the customer you've passed this on."

    conversation_id = f"conv_{tenant_id}_{customer_phone}"
    try:
        conversation = await inbox_repo.raise_escalation(
            conversation_id=conversation_id,
            tenant_id=tenant_id,
            reason=reason,
            summary=summary[:300],
        )
        await broadcast_conversation_updated(tenant_id, conversation)
        await raise_alert(
            get_database(),
            tenant_id,
            kind="customer_needs_you",
            title=f"{customer_phone} needs you",
            detail=f"{reason}: {summary[:200]}",
            severity="warning",
            ref={"customer_phone": customer_phone, "conversation_id": conversation_id},
        )
        return "Escalated to the owner. Tell the customer you've passed this on."
    except Exception as e:
        logger.error(f"Error escalating conversation {conversation_id}: {e}")
        await raise_alert(
            get_database(),
            tenant_id,
            kind="escalation_failed",
            title=f"A complaint from {customer_phone} could not be passed to you",
            detail="The customer was told to wait. Check the conversation now.",
            severity="critical",
            ref={"customer_phone": customer_phone},
        )
        return "Could not escalate right now. Apologise and ask the customer to wait."


@tool
async def send_form(form_name: str, message: Optional[str] = None, config: RunnableConfig = None) -> str:
    """Sends the customer one of the business's forms (listed under FORMS in your instructions).
    The customer fills it in inside WhatsApp, and their answers come back to you as a message
    starting with "[form submitted: ...]".

    Args:
        form_name: The form's name, exactly as listed.
        message: Optional short line shown with the form's button, in the customer's language.
    """
    from services.forms import find_published, send_form_to

    configurable = config.get("configurable", {}) if config else {}
    tenant_id = configurable.get("tenant_id")
    customer_phone = configurable.get("customer_phone")
    if not tenant_id or not customer_phone:
        return "Could not send the form: missing conversation context."
    if configurable.get("channel", "whatsapp") != "whatsapp":
        return "Forms only work on WhatsApp. Ask the questions in chat instead."

    db = get_database()
    doc = await find_published(db, tenant_id, form_name)
    if not doc:
        return f"There's no published form called '{form_name}'. Ask the questions in chat instead."
    if configurable.get("test_mode"):
        return f"TEST: the form '{doc['name']}' would be sent now. Nothing was sent."

    tenant = await db["tenants"].find_one({"tenant_id": tenant_id}) or {"tenant_id": tenant_id}
    result = await send_form_to(db, tenant, customer_phone, doc, message)
    if not result.ok:
        logger.warning(f"Form {doc['form_id']} not sent to {customer_phone}: {result.error_message}")
        return "The form could not be sent. Ask the questions in chat instead."
    return (
        f"The form '{doc['name']}' was sent. Tell the customer in one short line to tap the button and fill it in. "
        "Don't ask the same questions in chat while they do."
    )
