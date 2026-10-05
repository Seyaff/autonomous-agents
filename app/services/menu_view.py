"""
The menu as the agent and the customer see it: the owner's dish list, grouped by category.
Built from the clean dishes saved at upload, not from the raw PDF text, which comes out jumbled.

The layout is fixed here, not left to the model, so every reply shows the same clean list:
a bold category heading, then one bullet per dish with its price.
"""

from typing import Any, Dict, List, Optional, Tuple

from services.availability import MENU_ITEMS, normalize, today_for

MAX_DISHES = 60
UNCATEGORIZED = "Other"

# Used only when a dish came in without a real category (stored as "Other" or empty).
# First match wins, so the more specific words come first.
CATEGORY_RULES: List[Tuple[str, Tuple[str, ...]]] = [
    ("Karahi", ("karahi",)),
    ("BBQ & Kebabs", ("kebab", "seekh", "tikka", "boti", "bbq")),
    ("Rice", ("pulao", "biryani", "rice")),
    ("Burgers & Sandwiches", ("burger", "sandwich", "wrap")),
    ("Fries & Sides", ("fries", "nugget", "raita", "salad")),
    ("Breads", ("naan", "roti", "paratha")),
    ("Drinks", ("lassi", "kahwa", "lemonade", "juice", "shake", "tea", "drink", "cola", "coke", "water")),
]

# Display order for the usual categories. Anything else follows, alphabetically.
CATEGORY_ORDER = [name for name, _ in CATEGORY_RULES]


def _category_for(row: Dict[str, Any]) -> str:
    stored = (row.get("category") or "").strip()
    if stored and stored != UNCATEGORIZED:
        return stored
    name = (row.get("name") or "").lower()
    for category, words in CATEGORY_RULES:
        if any(word in name for word in words):
            return category
    return UNCATEGORIZED


def _sort_key(category: str) -> Tuple[int, str]:
    if category in CATEGORY_ORDER:
        return (CATEGORY_ORDER.index(category), category)
    return (len(CATEGORY_ORDER), category)


def _money(price: Any, currency: str) -> str:
    label = "Rs" if currency in ("", "PKR") else currency
    return f"{label} {price:,.0f}"


async def menu_text(db, tenant: Dict[str, Any], category: Optional[str] = None, now=None) -> str:
    """The dish list as a clean WhatsApp message, one block per category. Empty string if there's no dish list yet."""
    query: Dict[str, Any] = {"tenant_id": tenant["tenant_id"], "hidden": {"$ne": True}}
    rows = await db[MENU_ITEMS].find(query, {"_id": 0, "name": 1, "category": 1, "price": 1, "sold_out_on": 1, "hidden": 1}).sort([("category", 1), ("name", 1)]).to_list(length=500)
    if not rows:
        return ""

    today = today_for(tenant, now)
    currency = tenant.get("currency") or ""
    wanted = normalize(category) if category else None

    groups: Dict[str, List[str]] = {}
    sold_out: List[str] = []
    shown = 0
    for row in rows:
        cat = _category_for(row)
        if wanted and wanted not in normalize(cat):
            continue
        if row.get("sold_out_on") == today:
            sold_out.append(row["name"])
            continue
        if shown >= MAX_DISHES:
            continue
        price = row.get("price")
        price_text = f" — {_money(price, currency)}" if isinstance(price, (int, float)) else ""
        groups.setdefault(cat, []).append(f"• {row['name']}{price_text}")
        shown += 1

    if not groups and not sold_out:
        return f"No dishes match '{category}' on the menu."

    parts = [f"*{cat}*\n" + "\n".join(groups[cat]) for cat in sorted(groups, key=_sort_key)]
    if sold_out:
        parts.append("Sold out today: " + ", ".join(sold_out))
    return "\n\n".join(parts)
