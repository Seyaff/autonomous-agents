"""
The customer card: what the agent knows about one customer, built each turn.

Order history is derived from the `orders` collection (the source of truth),
not from counters that can drift. Facts come from `customer_facts`. The card
is rendered as a short block for the system prompt, so the cost per turn
stays roughly constant however long the customer has been ordering.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from memory.facts import list_active_facts

# Orders that count as the customer actually buying something.
COUNTED_STATUSES = ["accepted", "preparing", "out_for_delivery", "delivered"]
TOP_ITEMS = 5
MAX_FACTS_IN_PROMPT = 12


async def order_stats(db, tenant_id: str, customer_phone: str) -> Dict[str, Any]:
    base = {"tenant_id": tenant_id, "customer_phone": customer_phone}

    summary_cursor = await db["orders"].aggregate([
        {"$match": base},
        {"$group": {
            "_id": None,
            "total_orders": {"$sum": 1},
            "delivered_orders": {"$sum": {"$cond": [{"$eq": ["$status", "delivered"]}, 1, 0]}},
            "cancelled_orders": {"$sum": {"$cond": [{"$eq": ["$status", "cancelled"]}, 1, 0]}},
            "total_spent": {"$sum": {"$cond": [{"$in": ["$status", COUNTED_STATUSES]}, "$total_amount", 0]}},
            "first_order_at": {"$min": "$created_at"},
            "last_order_at": {"$max": "$created_at"},
        }},
    ])
    summary = (await summary_cursor.to_list(length=1) or [{}])[0]

    items_cursor = await db["orders"].aggregate([
        {"$match": {**base, "status": {"$in": COUNTED_STATUSES}}},
        {"$unwind": "$items"},
        {"$group": {"_id": "$items.name", "times": {"$sum": "$items.quantity"}}},
        {"$sort": {"times": -1}},
        {"$limit": TOP_ITEMS},
    ])
    favourites = [{"name": r["_id"], "quantity": r["times"]} for r in await items_cursor.to_list(length=TOP_ITEMS)]

    last = await db["orders"].find_one(base, sort=[("created_at", -1)])
    last_order = None
    if last:
        last_order = {
            "order_id": last.get("order_id"),
            "status": last.get("status"),
            "total_amount": last.get("total_amount"),
            "currency": last.get("currency"),
            "created_at": last.get("created_at"),
        }

    return {
        "total_orders": summary.get("total_orders", 0),
        "delivered_orders": summary.get("delivered_orders", 0),
        "cancelled_orders": summary.get("cancelled_orders", 0),
        "total_spent": round(summary.get("total_spent", 0.0), 2),
        "first_order_at": summary.get("first_order_at"),
        "last_order_at": summary.get("last_order_at"),
        "favourites": favourites,
        "last_order": last_order,
    }


async def build_customer_card(db, tenant_id: str, customer_phone: str) -> Dict[str, Any]:
    conversation = await db["conversations"].find_one(
        {"tenant_id": tenant_id, "customer_phone": customer_phone},
        {"customer_name": 1, "created_at": 1},
    )
    name = (conversation or {}).get("customer_name") or None
    first_seen = (conversation or {}).get("created_at")

    stats = await order_stats(db, tenant_id, customer_phone)
    facts = await list_active_facts(db, tenant_id, customer_phone, limit=MAX_FACTS_IN_PROMPT)

    return {
        "customer_phone": customer_phone,
        "name": name,
        "first_seen": first_seen,
        **stats,
        "facts": facts,
    }


def _fmt_date(value: Optional[datetime]) -> str:
    if not value:
        return "unknown"
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.strftime("%d %b %Y")


def render_card(card: Dict[str, Any]) -> str:
    """Short text block for the system prompt. Keep this compact: it is sent every turn."""
    lines: List[str] = ["Customer memory:"]
    lines.append(f"- Name: {card.get('name') or 'not known yet'}")

    if card.get("total_orders", 0) == 0:
        lines.append("- Orders: none yet (first-time customer)")
    else:
        last = card.get("last_order") or {}
        currency = last.get("currency") or ""
        lines.append(
            f"- Orders: {card['total_orders']} total, {card['delivered_orders']} delivered, "
            f"{card['cancelled_orders']} cancelled; spent {currency} {card['total_spent']:.0f}"
        )
        lines.append(f"- Customer since {_fmt_date(card.get('first_order_at'))}; "
                     f"last order {_fmt_date(card.get('last_order_at'))}")
        if card.get("favourites"):
            favs = ", ".join(f"{f['name']} (x{f['quantity']})" for f in card["favourites"])
            lines.append(f"- Usually orders: {favs}")
        if last:
            lines.append(f"- Last order {last.get('order_id')}: {last.get('status')}")

    facts = card.get("facts") or []
    if facts:
        lines.append("- Things to remember:")
        for f in facts:
            lines.append(f"  * [{f['kind']}] {f['value']}")

    lines.append(
        "Use this naturally. Don't recite it back, and don't mention these notes "
        "unless they help the customer."
    )
    return "\n".join(lines)
