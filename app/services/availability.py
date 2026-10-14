"""
Unavailable items. An item is sold out for one day, in the business's own timezone, and
comes back on its own the next day.
"""

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

MENU_ITEMS = "menu_items"


def today_for(tenant: Optional[Dict[str, Any]], now: Optional[datetime] = None) -> str:
    """Today's date (YYYY-MM-DD) in the business's timezone."""
    now = now or datetime.now(timezone.utc)
    try:
        tz = ZoneInfo((tenant or {}).get("timezone") or "UTC")
    except ZoneInfoNotFoundError:
        tz = timezone.utc
    return now.astimezone(tz).strftime("%Y-%m-%d")


def normalize(name: str) -> str:
    return re.sub(r"\s+", " ", (name or "").strip().lower())


async def sold_out_names(db, tenant: Dict[str, Any], now: Optional[datetime] = None) -> List[str]:
    """Names of items the agent must not offer or order right now: sold out today, or hidden by the owner.
    Never raises: a read failure means nothing is hidden."""
    try:
        cursor = db[MENU_ITEMS].find(
            {"tenant_id": tenant["tenant_id"], "$or": [{"sold_out_on": today_for(tenant, now)}, {"hidden": True}]},
            {"_id": 0, "name": 1},
        )
        return [row["name"] for row in await cursor.to_list(length=500) if row.get("name")]
    except Exception:
        return []


def is_sold_out(name: str, sold_out: List[str]) -> bool:
    wanted = normalize(name)
    return any(normalize(s) == wanted for s in sold_out)


async def catalog_prices(db, tenant_id: str) -> Dict[str, Dict[str, Any]]:
    """The owner's items keyed by normalized name: {"name", "price"}. Prices here beat any the model gives.
    Never raises: a read failure means no catalog prices, so the model's prices stand as before."""
    try:
        rows = await db[MENU_ITEMS].find(
            {"tenant_id": tenant_id}, {"_id": 0, "name": 1, "price": 1}
        ).to_list(length=1000)
    except Exception:
        return {}
    return {
        normalize(row["name"]): {"name": row["name"], "price": row.get("price")}
        for row in rows
        if row.get("name")
    }
