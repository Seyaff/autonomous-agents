from core.secrets import reveal
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional
from langchain_core.messages import SystemMessage, HumanMessage

from core.database import get_database
from core.settings import settings
from core.llm import get_chat_model
from core.whatsapp_utils import send_whatsapp_message
from core.ws_manager import ws_manager
from schemas.ws_events import WSEvent

logger = logging.getLogger(__name__)

llm = get_chat_model(purpose="weekly_report", temperature=0.3)


async def generate_7day_analytics(tenant_id: str) -> Dict[str, Any]:
    """Aggregates restaurant operations and sales metrics over the trailing 7 days."""
    db = get_database()
    now = datetime.now(timezone.utc)
    seven_days_ago = now - timedelta(days=7)
    fourteen_days_ago = now - timedelta(days=14)

    # 1. Fetch orders in the 7-day window
    query = {
        "tenant_id": tenant_id,
        "created_at": {"$gte": seven_days_ago}
    }
    cursor = db["orders"].find(query)
    orders = await cursor.to_list(length=5000)

    # Prior 7-day window, for revenue growth comparison
    prior_window_query = {
        "tenant_id": tenant_id,
        "created_at": {"$gte": fourteen_days_ago, "$lt": seven_days_ago},
        "status": {"$nin": ["cancelled", "pending"]},
    }
    prior_cursor = db["orders"].find(prior_window_query, {"total_amount": 1})
    prior_orders = await prior_cursor.to_list(length=5000)
    prior_revenue = sum(float(o.get("total_amount", 0.0)) for o in prior_orders)

    total_conversations = await db["conversations"].count_documents(
        {"tenant_id": tenant_id, "created_at": {"$gte": seven_days_ago}}
    )
    total_messages = await db["messages"].count_documents(
        {"tenant_id": tenant_id, "created_at": {"$gte": seven_days_ago}}
    )

    total_orders = len(orders)
    total_revenue = 0.0
    cancelled_orders = 0
    delivered_orders = 0
    item_counts: Dict[str, int] = {}
    unique_customers = set()

    for o in orders:
        st = o.get("status", "pending")
        amt = float(o.get("total_amount", 0.0))
        phone = o.get("customer_phone")
        if phone:
            unique_customers.add(phone)

        if st == "cancelled":
            cancelled_orders += 1
        elif st != "pending":
            # A pending order hasn't been accepted by the restaurant yet —
            # not real revenue any more than a cancelled one is.
            total_revenue += amt

        if st == "delivered":
            delivered_orders += 1

        for item in o.get("items", []):
            name = item.get("name", "Unknown")
            qty = int(item.get("quantity", 1))
            item_counts[name] = item_counts.get(name, 0) + qty

    # Calculate top items
    top_items = sorted(item_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    aov = (total_revenue / total_orders) if total_orders > 0 else 0.0
    cancellation_rate = ((cancelled_orders / total_orders) * 100) if total_orders > 0 else 0.0

    if prior_revenue > 0:
        revenue_growth_pct = ((total_revenue - prior_revenue) / prior_revenue) * 100
    else:
        revenue_growth_pct = 100.0 if total_revenue > 0 else 0.0

    return {
        "period_start": seven_days_ago.isoformat(),
        "period_end": now.isoformat(),
        "total_orders": total_orders,
        "total_revenue": round(total_revenue, 2),
        "revenue_growth_pct": round(revenue_growth_pct, 1),
        "delivered_orders": delivered_orders,
        "cancelled_orders": cancelled_orders,
        "cancellation_rate": round(cancellation_rate, 1),
        "average_order_value": round(aov, 2),
        "unique_customers": len(unique_customers),
        "top_items": top_items,
        "total_conversations": total_conversations,
        "total_messages": total_messages,
    }


async def compile_and_send_weekly_report(tenant_id: str) -> Dict[str, Any]:
    """
    Autonomous Agent that compiles a 7-day executive summary and proactively
    notifies the restaurant owner on WhatsApp with actionable recommendations.
    """
    db = get_database()
    tenant = await db["tenants"].find_one({"tenant_id": tenant_id})
    if not tenant:
        raise ValueError(f"Tenant {tenant_id} not found.")

    business_name = tenant.get("business_name") or tenant.get("name") or "Your Restaurant"
    currency = tenant.get("currency", "USD")
    owner_phone = tenant.get("owner_whatsapp_number") or tenant.get("business_phone")

    metrics = await generate_7day_analytics(tenant_id)

    top_items_text = "\n".join([f"  • {name}: {qty} orders" for name, qty in metrics["top_items"]]) or "  • None recorded yet"

    # LLM Synthesizer compiles high-impact weekly briefing
    system_prompt = (
        "You are an expert hospitality business consultant and operations intelligence agent. "
        "Review the restaurant's trailing 7-day performance metrics and write a crisp, professional, "
        "and encouraging executive summary for the restaurant owner. Include 3 strategic, actionable tips "
        "to increase revenue, reduce cancellations, or promote best-selling dishes next week."
    )

    human_prompt = f"""Restaurant: {business_name}
Trailing 7-Day Performance:
- Total Orders Placed: {metrics['total_orders']}
- Total Revenue: {currency} {metrics['total_revenue']}
- Completed Deliveries: {metrics['delivered_orders']}
- Cancelled Orders: {metrics['cancelled_orders']} ({metrics['cancellation_rate']}%)
- Average Order Value: {currency} {metrics['average_order_value']}
- Unique Customers Served: {metrics['unique_customers']}
- Top Selling Dishes:
{top_items_text}

Please provide:
1. Executive Performance Highlights
2. Operational Analysis (Cancellations & Bottlenecks)
3. 3 Actionable Recommendations for Next Week
Format cleanly for WhatsApp reading with bold headers and bullet points.
"""

    response = await llm.ainvoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=human_prompt)
    ])
    report_text = response.content

    # Save report to database
    report_doc = {
        "tenant_id": tenant_id,
        "business_name": business_name,
        "metrics": metrics,
        "summary": report_text,
        "created_at": datetime.now(timezone.utc),
        "delivered_via_whatsapp": False,
    }

    inserted = await db["weekly_reports"].insert_one(report_doc)
    report_doc["_id"] = str(inserted.inserted_id)

    # Proactive Autopilot Dispatch to Owner's WhatsApp
    if owner_phone:
        token = reveal(tenant.get("whatsapp_access_token")) or settings.WHATSAPP_TOKEN
        phone_id = tenant.get("phone_number_id") or settings.WHATSAPP_PHONE_NUMBER_ID
        whatsapp_message = (
            f"📊 *7-DAY AUTOPILOT BUSINESS REPORT: {business_name.upper()}*\n\n"
            f"{report_text}\n\n"
            f"💡 *Generated automatically by your AI Business Autopilot.*"
        )
        sent = await send_whatsapp_message(
            to_phone=owner_phone,
            text=whatsapp_message,
            token=token,
            phone_number_id=phone_id
        )
        if sent:
            await db["weekly_reports"].update_one(
                {"_id": inserted.inserted_id},
                {"$set": {"delivered_via_whatsapp": True}}
            )

    # Broadcast event to frontend dashboard
    await ws_manager.broadcast_to_tenant(
        tenant_id,
        WSEvent(type="report.weekly_generated", payload={"report": report_doc}),
    )

    return report_doc
