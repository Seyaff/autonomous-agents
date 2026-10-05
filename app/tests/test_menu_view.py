"""The dish list the agent reads: grouped, priced, and without hidden or sold-out dishes.

Run from the app folder:
    uv run --with pytest python -m pytest tests -q
"""

import asyncio
from datetime import datetime, timezone

from services.menu_view import menu_text

NOW = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)
TENANT = {"tenant_id": "t1", "timezone": "UTC", "currency": "PKR"}


class FakeQuery:
    def __init__(self, rows):
        self.rows = rows

    def sort(self, *_):
        return self

    async def to_list(self, length=None):
        return list(self.rows)


class FakeCollection:
    def __init__(self, rows):
        self.rows = rows

    def find(self, query, projection=None):
        matches = [r for r in self.rows if r["tenant_id"] == query["tenant_id"] and r.get("hidden") is not True]
        return FakeQuery(sorted(matches, key=lambda r: (r.get("category") or "", r["name"])))


def db_with(rows):
    return {"menu_items": FakeCollection(rows)}


def dish(name, category="Mains", price=1200, **extra):
    return {"tenant_id": "t1", "name": name, "category": category, "price": price, **extra}


def test_dishes_are_grouped_by_category_with_prices():
    db = db_with([dish("Chicken Karahi"), dish("Naan", "Breads", 40)])
    text = asyncio.run(menu_text(db, TENANT))
    assert "*Mains*" in text and "• Chicken Karahi — Rs 1,200" in text
    assert "*Breads*" in text and "• Naan — Rs 40" in text


def test_hidden_dishes_are_left_out():
    db = db_with([dish("Chicken Karahi"), dish("Old Dish", hidden=True)])
    assert "Old Dish" not in asyncio.run(menu_text(db, TENANT))


def test_sold_out_today_is_listed_separately():
    db = db_with([dish("Chicken Karahi", sold_out_on="2026-10-03"), dish("Naan", "Breads", 40)])
    text = asyncio.run(menu_text(db, TENANT, now=NOW))
    assert "• Chicken Karahi" not in text
    assert "Sold out today: Chicken Karahi" in text


def test_a_category_filter_narrows_the_list():
    db = db_with([dish("Chicken Karahi"), dish("Naan", "Breads", 40)])
    text = asyncio.run(menu_text(db, TENANT, "breads"))
    assert "Naan" in text and "Karahi" not in text


def test_no_dish_list_gives_an_empty_answer():
    assert asyncio.run(menu_text(db_with([]), TENANT)) == ""


def test_dishes_without_a_category_are_grouped_by_name():
    db = db_with([dish("Chicken Karahi", "Other"), dish("Plain Naan", "", 70), dish("Mint Lemonade", "Other", 260)])
    text = asyncio.run(menu_text(db, TENANT))
    assert "*Karahi*" in text and "• Chicken Karahi" in text
    assert "*Breads*" in text and "• Plain Naan — Rs 70" in text
    assert "*Drinks*" in text and "• Mint Lemonade — Rs 260" in text


def test_generic_descriptions_are_not_shown():
    db = db_with([dish("Chicken Karahi", "Mains", description="Fresh karahi cooking.")])
    assert "Fresh karahi cooking" not in asyncio.run(menu_text(db, TENANT))


def test_owner_categories_are_kept_as_they_are():
    db = db_with([dish("Chicken Karahi", "Specials")])
    assert "*Specials*" in asyncio.run(menu_text(db, TENANT))
