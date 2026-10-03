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
from core.settings import settings
from core.events import broadcast_order_update
from memory.customer_memory import update_customer_profile
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
    total_amount: float,
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
        total_amount: Final calculated total cost for the customer.
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

        now = datetime.now(timezone.utc)
        order_document = {
            "order_id": order_id,
            "tenant_id": tenant_id,
            "customer_phone": customer_phone,
            "customer_name": customer_name,
            "delivery_address": delivery_address,
            "items": formatted_items,
            "total_amount": float(total_amount),
            "payment_method": payment_method,
            "customer_notes": customer_notes,
            "status": "pending",  # pending, accepted, preparing, out_for_delivery, delivered, cancelled
            "created_at": now,
            "updated_at": now,
        }

        result = await db["orders"].insert_one(order_document)

        if result.inserted_id:
            order_document["_id"] = str(result.inserted_id)
            # Update customer's long-term profile
            try:
                await update_customer_profile(
                    tenant_id=tenant_id,
                    customer_phone=customer_phone,
                    name=customer_name,
                    delivery_address=delivery_address,
                    notes=customer_notes,
                    order_amount=float(total_amount),
                    favorite_items=item_names,
                )
            except Exception as pe:
                logger.warning(f"Could not update customer profile: {pe}")

            # Push real-time event to owner dashboard
            try:
                await broadcast_order_update(
                    tenant_id=tenant_id,
                    event_type="order.created",
                    order_data=order_document
                )
            except Exception as be:
                logger.warning(f"Could not broadcast order update: {be}")

            items_summary = ", ".join([f"{i['quantity']}x {i['name']}" for i in formatted_items])
            return (
                f"Order placed successfully! Reference ID: {order_id}.\n"
                f"Items: {items_summary}\n"
                f"Total Amount: {currency} {total_amount:.2f}\n"
                f"Delivery Address: {delivery_address}\n"
                f"Payment Method: {payment_method.upper()}\n"
                f"Status: PENDING confirmation by the restaurant."
            )

        return "Database error: Could not record order in database."

    except PyMongoError as e:
        logger.error(f"PyMongo error in create_order_tool: {e}")
        return f"Database error creating order: {str(e)}"
    except Exception as e:
        logger.error(f"Unexpected error in create_order_tool: {e}")
        return f"Failed to place order: {str(e)}"


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
            f"- Total: ${total:.2f}\n"
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

    conversation_id = f"conv_{tenant_id}_{customer_phone}"
    try:
        conversation = await inbox_repo.raise_escalation(
            conversation_id=conversation_id,
            tenant_id=tenant_id,
            reason=reason,
            summary=summary[:300],
        )
        await broadcast_conversation_updated(tenant_id, conversation)
        return "Escalated to the restaurant. Tell the customer you've passed this to the restaurant."
    except Exception as e:
        logger.error(f"Error escalating conversation {conversation_id}: {e}")
        return "Could not escalate right now. Apologise and ask the customer to wait."
