"""
Turns a menu's text into structured dishes, so the setup screen can show them.

The menu is still indexed for search (Pinecone) as before. This adds a
structured list on top: name, category, price and description.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field, ValidationError, field_validator

from core.llm import get_chat_model

logger = logging.getLogger(__name__)

MENU_ITEMS = "menu_items"
MAX_TEXT_CHARS = 60_000
MAX_ITEMS = 400

EXTRACTION_PROMPT = """Extract the dishes from this restaurant menu.

Return JSON only, in this shape:
{"items": [{"name": "...", "category": "...", "price": 0.0, "description": "..."}]}

Rules:
- One entry per dish. Use the dish's name as printed.
- category is the section heading it sits under (e.g. "Burgers", "Drinks"). Use "Other" if there is none.
- price is a number in the menu's currency with no symbol. Use null if no price is shown.
- description is short, or "" if none.
- Skip prices-only lines, opening hours, addresses and promotions that aren't dishes.

Menu text:
{menu}"""


class MenuItem(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    category: str = Field(default="Other", max_length=60)
    price: Optional[float] = Field(default=None, ge=0)
    description: str = Field(default="", max_length=300)

    @field_validator("name", "category", "description", mode="before")
    @classmethod
    def _text(cls, v: Any) -> Any:
        return v.strip() if isinstance(v, str) else v

    @field_validator("category", mode="after")
    @classmethod
    def _category(cls, v: str) -> str:
        return v or "Other"


def _parse_items(text: str) -> List[Dict[str, Any]]:
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object in model reply")
    data = json.loads(text[start:end + 1])
    raw = data.get("items", []) if isinstance(data, dict) else []
    if not isinstance(raw, list):
        raise ValueError("items is not a list")
    return raw


async def extract_menu_items(menu_text: str) -> List[Dict[str, Any]]:
    """Returns validated items. Raises if the model's reply can't be used at all.
    Individual bad entries are dropped and logged, not fatal."""
    text = (menu_text or "").strip()
    if not text:
        return []

    model = get_chat_model(purpose="menu_extractor", temperature=0.0)
    response = await model.ainvoke([
        SystemMessage(content="You output strict JSON for a restaurant menu system."),
        # replace, not format: the prompt contains literal JSON braces.
        HumanMessage(content=EXTRACTION_PROMPT.replace("{menu}", text[:MAX_TEXT_CHARS])),
    ])

    items: List[Dict[str, Any]] = []
    for raw in _parse_items(str(response.content))[:MAX_ITEMS]:
        try:
            items.append(MenuItem(**raw).model_dump())
        except (ValidationError, TypeError) as e:
            logger.info(f"Dropped menu entry {raw!r}: {e}")
    return items


async def replace_menu_items(db, tenant_id: str, doc_id: str, items: List[Dict[str, Any]]) -> int:
    """Swaps the tenant's dishes for the ones from this menu. Returns how many were saved."""
    now = datetime.now(timezone.utc)
    await db[MENU_ITEMS].delete_many({"tenant_id": tenant_id})
    if items:
        await db[MENU_ITEMS].insert_many([
            {**item, "tenant_id": tenant_id, "doc_id": doc_id, "created_at": now}
            for item in items
        ])
    return len(items)
