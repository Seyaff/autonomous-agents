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
from services.order_service import compute_totals, initial_status_entry
from services.order_confirmation import AWAITING, find_awaiting, send_summary
from services.availability import is_sold_out, sold_out_names
from core.setup_state import hours_status
from core.settings import settings
from core.events import broadcast_order_update
from services.pdf_ingestion import embedding_model
from langchain_pinecone import PineconeVectorStore

logger = logging.getLogger(__name__)


from services.knowledge_ingestion import search_tenant_knowledge

@tool
async def search_uploaded_documents(query: str, config: RunnableConfig) -> str:
    """Searches the restaurant's uploaded menus, pricing sheets, deals, and policies for factual answers.
    ALWAYS call this tool first before answering customer questions about food, deals, prices, or policies.
    """
    configurable = config.get("configurable", {})
    tenant_id = configurable.get("tenant_id")
    if not tenant_id:
        return "System notice: Restaurant tenant ID missing from context. Cannot query menu."

    return await search_tenant_knowledge(query=query, tenant_id=tenant_id, top_k=4)


@tool
async def create_order_tool(
    delivery_address: str,
    items: List[Dict[str, Any]],
    payment_method: str = "cod",
    customer_notes: Optional[str] = None,
    customer_name: Optional[str] = None,
    config: RunnableConfig = None
) -> str:
    """Creates and saves a new customer order to the database.
    
    Args:
        delivery_address: Destination delivery address provided by the customer.
        items: List of ordered dishes/items. Each dict MUST contain 'name', 'quantity', and 'price'.
               Example: [{"name": "Chicken Biryani", "quantity": 2, "price": 14.0}]
        The total (including delivery) is calculated by the system, not by you.
        payment_method: Payment method chosen by customer ('cod', 'card', 'cash'). Default is 'cod'.
        customer_notes: Optional special instructions (e.g. 'extra spicy', 'no onions').
        customer_name: Optional customer name if provided.
    """
    configurable = config.get("configurable", {}) if config else {}
    tenant_id = configurable.get("tenant_id", "default_tenant")
    customer_phone = configurable.get("customer_phone", "unknown_customer")

    try:
        db = get_database()
        order_id = f"ORD-{uuid.uuid4().hex[:8].upper()}"

        tenant_doc = await db["tenants"].find_one({"tenant_id": tenant_id})
        currency = (tenant_doc or {}).get("currency") or "USD"

        # Hard rule, not just prompt guidance: no orders while the restaurant is shut.
        open_state = hours_status(
            (tenant_doc or {}).get("operating_hours") or [],
            (tenant_doc or {}).get("timezone") or "UTC",
        )
        if not open_state["open_now"]:
            opens = open_state.get("opens_next") or "later"
            return (
                f"The restaurant is closed right now. Next opening: {opens}. "
                "Don't place the order. Tell the customer when we open."
            )

        formatted_items = []
        item_names = []
        for item in items:
            name = str(item.get("name", "Unknown Item"))
            qty = int(item.get("quantity", 1))
            price = float(item.get("price", 0.0))
            formatted_items.append({
                "name": name,
                "quantity": qty,
                "price": price,
                "notes": item.get("notes")
            })
            item_names.append(name)

        # Sold-out dishes are refused here too, not only in the prompt.
        sold_out = await sold_out_names(db, tenant_doc or {"tenant_id": tenant_id})
        blocked = [i["name"] for i in formatted_items if is_sold_out(i["name"], sold_out)]
        if blocked:
            return (
                f"Sold out today: {', '.join(blocked)}. Don't place the order with them. "
                "Tell the customer and ask them to pick something else."
            )

        subtotal, delivery_fee, total_amount, eta_minutes = compute_totals(formatted_items, tenant_doc)

        minimum = float((tenant_doc or {}).get("min_order_amount") or 0)
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
                await send_summary(db, tenant_doc or {"tenant_id": tenant_id}, waiting)
                return (
                    "An order is already waiting for the customer's answer. The summary was sent again. "
                    "Don't place another one; wait for them to tap Confirm."
                )

        if configurable.get("test_mode"):
            # Test chat: show what would happen, change nothing.
            test_items = ", ".join(f"{i['quantity']}x {i['name']}" for i in formatted_items)
            return (
                f"Order placed. Reference ID: TEST-{uuid.uuid4().hex[:6].upper()} (test chat, not saved).\n"
                f"Items: {test_items}\n"
                f"Subtotal: {currency} {subtotal:.2f}, Delivery: {currency} {delivery_fee:.2f}\n"
                f"Total Amount: {currency} {total_amount:.2f}\n"
                f"Estimated time: about {eta_minutes} minutes"
            )
        now = datetime.now(timezone.utc)
        order_document = {
            "order_id": order_id,
            "tenant_id": tenant_id,
            "customer_phone": customer_phone,
            "customer_name": customer_name.strip(),
            "conversation_id": f"conv_{tenant_id}_{customer_phone}",
            "source": "ai_agent",
            "delivery_address": delivery_address,
            "items": formatted_items,
            "currency": currency,
            "subtotal": subtotal,
            "delivery_fee": delivery_fee,
            "total_amount": total_amount,
            "eta_minutes": eta_minutes,
            "payment_method": payment_method,
            "customer_notes": customer_notes,
            # Not placed until the customer taps Confirm.
            "status": AWAITING,
            "status_history": [initial_status_entry(now, by="agent")],
            "created_at": now,
            "updated_at": now,
        }

        result = await db["orders"].insert_one(order_document)
        if not result.inserted_id:
            return "Database error: Could not save the order draft."

        sent = await send_summary(db, tenant_doc or {"tenant_id": tenant_id}, order_document)
        if not sent.ok:
            logger.warning(f"Order summary for {order_id} could not be sent: {sent.error_message}")
            await db["orders"].update_one({"order_id": order_id}, {"$set": {"status": "cancelled", "cancellation_reason": "Summary not delivered"}})
            return "The order summary could not be sent to the customer. Ask them to send their order again."

        return (
            f"Summary sent to the customer with Confirm and Cancel buttons (order {order_id}). "
            "The order is NOT placed yet. Do not say it is placed or confirmed. "
            "Ask the customer to tap Confirm, and say the restaurant will get it once they do."
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
    """Checks the status of the customer's current or recent orders.
    
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
        address = order.get("delivery_address", "Pickup/Takeaway")
        created = order.get("created_at")
        time_str = created.strftime("%Y-%m-%d %H:%M UTC") if isinstance(created, datetime) else "Recently"

        return (
            f"Order Details for {ref}:\n"
            f"- Status: {status}\n"
            f"- Placed At: {time_str}\n"
            f"- Items: {items_summary}\n"
            f"- Total: {order.get('currency', 'USD')} {total:.2f}\n"
            f"- Delivery To: {address}"
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
    """Cancels a customer order if it has not yet left the kitchen.
    
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
    """Hands this customer's chat to the restaurant owner. Use it for refund
    requests, complaints, requests to speak to a person, and anything you
    cannot resolve from the menu or order tools. After calling it, tell the
    customer you've passed this to the restaurant and a person will follow up.

    Args:
        reason: Why it needs a person: refund, complaint, human_requested, agent_failed, other.
        summary: One line for the owner, e.g. "Wants refund for cold biryani, ORD-6A21".
    """
    configurable = config.get("configurable", {}) if config else {}
    tenant_id = configurable.get("tenant_id")
    customer_phone = configurable.get("customer_phone")
    if not tenant_id or not customer_phone:
        return "Could not escalate: missing conversation context."

    if configurable.get("test_mode"):
        return "Escalated to the restaurant. Tell the customer you've passed this to the restaurant."

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
        return "Escalated to the restaurant. Tell the customer you've passed this to the restaurant."
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
