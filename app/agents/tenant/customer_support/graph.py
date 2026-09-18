import json
import uuid
import logging
from typing import Dict, Any, List, Optional
from sqlalchemy import select
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.graph import StateGraph, END
from app.config import settings
from app.core.database import AsyncSessionLocal
from app.models.tenant import Tenant
from app.agents.tenant.customer_support.state import CustomerSupportState, CartItem
from app.agents.tenant.customer_support.prompts import CUSTOMER_SUPPORT_SYSTEM_PROMPT
from app.agents.tenant.customer_support.tools import (
    search_menu_items,
    create_confirmed_order,
    get_active_customer_order
)

logger = logging.getLogger(__name__)

# In-memory session state storage (backed by Redis in production)
_active_sessions: Dict[str, CustomerSupportState] = {}

def get_or_create_session(tenant_id: str, sender_phone: str) -> CustomerSupportState:
    session_key = f"{tenant_id}:{sender_phone}"
    if session_key not in _active_sessions:
        _active_sessions[session_key] = {
            "messages": [],
            "tenant_id": tenant_id,
            "customer_id": None,
            "sender_phone": sender_phone,
            "cart": [],
            "delivery_address": None,
            "delivery_type": "delivery",
            "order_id": None,
            "escalation_needed": False,
            "escalation_reason": None
        }
    return _active_sessions[session_key]

def get_model():
    """Returns available LLM instance (ChatGroq, Gemini, or OpenAI) with fallback."""
    if settings.GROQ_API_KEY:
        try:
            from langchain_groq import ChatGroq
            return ChatGroq(
                model_name="openai/gpt-oss-120b",
                groq_api_key=settings.GROQ_API_KEY,
                temperature=0.2
            )
        except Exception as e:
            logger.warning(f"Could not load ChatGroq model: {e}")

    if settings.GOOGLE_API_KEY and not settings.GOOGLE_API_KEY.startswith("AQ."):
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            return ChatGoogleGenerativeAI(
                model="gemini-1.5-flash-latest",
                google_api_key=settings.GOOGLE_API_KEY,
                temperature=0.2
            )
        except Exception as e:
            logger.warning(f"Could not load Gemini model: {e}")

    if settings.OPENAI_API_KEY:
        try:
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model="gpt-4o-mini",
                api_key=settings.OPENAI_API_KEY,
                temperature=0.2
            )
        except Exception as e:
            logger.warning(f"Could not load OpenAI model: {e}")

    return None

async def run_customer_support_graph(
    tenant_id: str,
    sender_phone: str,
    user_message: str
) -> str:
    """Executes the customer support conversation flow and returns the text response."""
    session = get_or_create_session(tenant_id, sender_phone)
    
    # 1. Fetch tenant information
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(Tenant).where(Tenant.id == uuid.UUID(tenant_id)))
        tenant = res.scalar_one_or_none()
        restaurant_name = tenant.name if tenant else "Our Restaurant"
        currency = tenant.currency if tenant else "USD"
        address = tenant.address or "Downtown"
        opening_hours = tenant.opening_hours or "10:00 AM - 11:00 PM"

    # 2. Get available menu items for context
    menu_items = await search_menu_items(tenant_id)
    menu_catalog_str = "\n".join([
        f"- {item['name']}: Rs. {item['price']:.0f} ({item['description']})"
        for item in menu_items
    ]) or "No items currently on the menu."

    cart_summary = "\n".join([
        f"- {it['quantity']}x {it['name']} @ Rs. {it['price']:.0f} each"
        for it in session["cart"]
    ]) or "Cart is empty."
    cart_total = sum(it["price"] * it["quantity"] for it in session["cart"])

    # 3. Fetch active / recent order from database (Ground truth memory)
    active_order = await get_active_customer_order(tenant_id, sender_phone)
    active_order_context = ""
    if active_order:
        items_line = ", ".join([f"{it['quantity']}x {it['name']}" for it in active_order["items"]])
        active_order_context = (
            f"\n\nACTIVE ORDER ON FILE FOR THIS CUSTOMER:\n"
            f"- Order Number: {active_order['order_number']}\n"
            f"- Placed At: {active_order['created_at']}\n"
            f"- Status: {active_order['status']}\n"
            f"- Items: {items_line}\n"
            f"- Total: Rs. {active_order['total_amount']:.0f}\n"
            f"- Address: {active_order['delivery_address'] or 'Standard Delivery'}\n"
            "CUSTOMER REMINDER: Customer ka yeh order already system mein majood hai! Agar customer order status, confirmation ya delivery time pooche, to foran yeh exact details bata kar mutma'in karein!"
        )

    system_prompt = CUSTOMER_SUPPORT_SYSTEM_PROMPT.format(
        restaurant_name=restaurant_name,
        currency="Rs.",
        address=address,
        opening_hours=opening_hours
    ) + f"\n\nCURRENT MENU:\n{menu_catalog_str}\n\nCURRENT CUSTOMER CART:\n{cart_summary}\nCart Total: Rs. {cart_total:.0f}{active_order_context}"

    model = get_model()

    # If an LLM is available, invoke it with LangChain
    if model:
        messages = [SystemMessage(content=system_prompt)]
        # Add last 6 messages of conversation context
        messages.extend(session["messages"][-6:])
        messages.append(HumanMessage(content=user_message))

        try:
            ai_response = await model.ainvoke(messages)
            reply_text = ai_response.content

            # Check if customer wants to finalize order
            lower_msg = user_message.lower()
            if any(word in lower_msg for word in ["checkout", "confirm order", "place order", "buy now", "order confirm"]):
                if session["cart"]:
                    order_result = await create_confirmed_order(
                        tenant_id=tenant_id,
                        customer_phone=sender_phone,
                        cart_items=session["cart"],
                        delivery_address=session.get("delivery_address") or "Standard Delivery",
                        delivery_type=session.get("delivery_type", "delivery")
                    )
                    reply_text += (
                        f"\n\n🎉 *Order Confirmed! {order_result['order_number']}*\n"
                        f"Total: Rs. {order_result['total_amount']:.0f} (Paid via Instant Dummy Payment)\n"
                        f"Estimated Delivery: {order_result['estimated_delivery_minutes']} mins.\n"
                        "Kitchen ne aapka order receive kar liya hai aur tayyari shuru hai! 🍳"
                    )
                    session["cart"] = []

            # Save to session history
            session["messages"].append(HumanMessage(content=user_message))
            session["messages"].append(AIMessage(content=reply_text))
            return reply_text
        except Exception as e:
            logger.error(f"Error calling LLM: {e}")

    # Deterministic fallback logic (runs without external API keys!)
    lower_msg = user_message.lower()
    
    # Check for Menu request
    if any(k in lower_msg for k in ["menu", "food", "what do you have", "dishes", "list"]):
        reply = f"🍽️ *Welcome to {restaurant_name}!*\nHere is our current menu:\n\n{menu_catalog_str}\n\nTo add any item to your cart, just reply with the item name!"
        session["messages"].append(HumanMessage(content=user_message))
        session["messages"].append(AIMessage(content=reply))
        return reply

    # Check for ordering/adding item
    matched_item = None
    for item in menu_items:
        if item["name"].lower() in lower_msg:
            matched_item = item
            break

    if matched_item and any(k in lower_msg for k in ["add", "order", "want", "get", "1", "2"]):
        session["cart"].append({
            "menu_item_id": matched_item["id"],
            "name": matched_item["name"],
            "price": matched_item["price"],
            "quantity": 1,
            "notes": None
        })
        new_total = sum(it["price"] * it["quantity"] for it in session["cart"])
        reply = (
            f"✅ Added *{matched_item['name']}* (${matched_item['price']:.2f}) to your cart!\n"
            f"🛒 *Current Cart Total:* ${new_total:.2f}\n\n"
            "Would you like anything else, or should we *checkout*?"
        )
        session["messages"].append(HumanMessage(content=user_message))
        session["messages"].append(AIMessage(content=reply))
        return reply

    # Check for Cart view
    if any(k in lower_msg for k in ["cart", "items in my cart", "my order"]):
        if not session["cart"]:
            return "Your cart is currently empty! Would you like to view our *menu*?"
        reply = f"🛒 *Your Current Cart:*\n{cart_summary}\n*Total:* ${cart_total:.2f}\n\nReply with *checkout* to place your order!"
        return reply

    # Check for Checkout
    if any(k in lower_msg for k in ["checkout", "confirm", "place order", "pay"]):
        if not session["cart"]:
            return "Your cart is empty! Please select an item from our *menu* first."
        
        order_result = await create_confirmed_order(
            tenant_id=tenant_id,
            customer_phone=sender_phone,
            cart_items=session["cart"],
            delivery_address=session.get("delivery_address") or "Customer WhatsApp Address",
            delivery_type=session.get("delivery_type", "delivery")
        )
        session["cart"] = []
        return (
            f"🎉 *Order Placed Successfully!*\n"
            f"Order Number: *{order_result['order_number']}*\n"
            f"Total Paid: *${order_result['total_amount']:.2f}* (via Instant Dummy Payment)\n"
            f"Estimated Arrival: *{order_result['estimated_delivery_minutes']} minutes*\n\n"
            "Thank you for ordering with us! We will notify you when it's on the way."
        )

    # General greeting fallback
    reply = f"👋 Hello! Welcome to *{restaurant_name}* on WhatsApp.\nHow can I help you today? You can reply with *menu* to see our dishes or ask any question!"
    session["messages"].append(HumanMessage(content=user_message))
    session["messages"].append(AIMessage(content=reply))
    return reply
