"""
The menu as the agent and the customer see it: the owner's dish list, grouped by category.
Built from the clean dishes saved at upload, not from the raw PDF text, which comes out jumbled.
"""

from typing import Any, Dict, List, Optional

from services.availability import MENU_ITEMS, normalize, today_for

MAX_DISHES = 60
UNCATEGORIZED = "Other"


async def menu_text(db, tenant: Dict[str, Any], category: Optional[str] = None, now=None) -> str:
    """The dish list as short lines, one block per category. Empty string if there's no dish list yet."""
    query: Dict[str, Any] = {"tenant_id": tenant["tenant_id"], "hidden": {"$ne": True}}
    rows = await db[MENU_ITEMS].find(query, {"_id": 0, "name": 1, "category": 1, "price": 1, "description": 1, "sold_out_on": 1, "hidden": 1}).sort([("category", 1), ("name", 1)]).to_list(length=500)
    if not rows:
        return ""

    today = today_for(tenant, now)
    currency = tenant.get("currency") or ""
    wanted = normalize(category) if category else None

    groups: Dict[str, List[str]] = {}
    sold_out: List[str] = []
    shown = 0
    for row in rows:
        cat = row.get("category") or UNCATEGORIZED
        if wanted and wanted not in normalize(cat):
            continue
        if row.get("sold_out_on") == today:
            sold_out.append(row["name"])
            continue
        if shown >= MAX_DISHES:
            continue
        price = row.get("price")
        price_text = f" — {currency} {price:,.0f}" if isinstance(price, (int, float)) else ""
        line = f"- {row['name']}{price_text}"
        if row.get("description"):
            line += f" ({row['description'][:80]})"
        groups.setdefault(cat, []).append(line)
        shown += 1

    if not groups and not sold_out:
        return f"No dishes match '{category}' on the menu."

    parts = [f"{cat}:\n" + "\n".join(lines) for cat, lines in groups.items()]
    if sold_out:
        parts.append("Sold out today: " + ", ".join(sold_out))
    return "\n\n".join(parts)
