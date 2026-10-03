"""
Turns a menu's text into structured dishes, so the setup screen can show them.

The menu is still indexed for search (Pinecone) as before. This adds a
structured list on top: name, category, price and description.

Long menus are read in chunks. A single request that is too large, or that hits
a per-minute token limit, fails on some providers. Chunks are read one at a time,
and a rate-limit error waits and retries rather than failing the upload.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field, ValidationError, field_validator

from core.llm import get_chat_model
from core.settings import settings

logger = logging.getLogger(__name__)

MENU_ITEMS = "menu_items"
CHUNK_CHARS = 5000        # about 1,500 tokens per request, well under per-minute limits
MAX_CHUNKS = 40           # 200k characters, more than any printed menu
MAX_ITEMS = 400
RETRY_WAIT_SECONDS = 20
MAX_ATTEMPTS = 6

# on_progress(parts_done, parts_total, note). note is set while the job waits on the model.
ProgressCallback = Callable[[int, int, Optional[str]], Awaitable[None]]

EXTRACTION_PROMPT = """Extract the dishes from this part of a restaurant menu.

Return JSON only, in this shape:
{"items": [{"name": "...", "category": "...", "price": 0.0, "description": "..."}]}

Rules:
- One entry per dish. Use the dish's name as printed.
- category is the section heading it sits under (e.g. "Burgers", "Drinks"). Use "Other" if there is none.
- price is a number in the menu's currency with no symbol. Use null if no price is shown.
- description is short, or "" if none.
- Skip prices-only lines, opening hours, addresses and promotions that aren't dishes.
- If this part has no dishes, return {"items": []}.

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


def chunk_text(text: str, size: int = CHUNK_CHARS) -> List[str]:
    """Splits on paragraph breaks so a dish's name and price stay together.
    A single paragraph longer than `size` is split hard."""
    chunks: List[str] = []
    current = ""
    for paragraph in text.split("\n\n"):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        while len(paragraph) > size:
            if current:
                chunks.append(current)
                current = ""
            chunks.append(paragraph[:size])
            paragraph = paragraph[size:]
        if len(current) + len(paragraph) + 2 > size and current:
            chunks.append(current)
            current = paragraph
        else:
            current = f"{current}\n\n{paragraph}" if current else paragraph
    if current:
        chunks.append(current)
    return chunks[:MAX_CHUNKS]


def _menu_model():
    if (settings.LLM_PROVIDER or "groq").lower() == "openai":
        return get_chat_model(purpose="menu_extractor", temperature=0.0, model=settings.MENU_OPENAI_MODEL)
    return get_chat_model(purpose="menu_extractor", temperature=0.0, model=settings.MENU_GROQ_MODEL)


def _parse_items(text: str) -> List[Dict[str, Any]]:
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object in model reply")
    data = json.loads(text[start:end + 1])
    raw = data.get("items", []) if isinstance(data, dict) else []
    if not isinstance(raw, list):
        raise ValueError("items is not a list")
    return raw


def _is_rate_limit(err: Exception) -> bool:
    text = str(err).lower()
    return "rate_limit" in text or "429" in text or "413" in text or "too large" in text


async def _ask_chunk(model, chunk: str, on_wait: Callable[[str], Awaitable[None]]) -> str:
    """One model call for one part. Waits and retries on rate limits, and says so while it waits."""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = await model.ainvoke([
                SystemMessage(content="You output strict JSON for a restaurant menu system."),
                HumanMessage(content=EXTRACTION_PROMPT.replace("{menu}", chunk)),
            ])
            return str(response.content)
        except Exception as err:
            if attempt < MAX_ATTEMPTS and _is_rate_limit(err):
                logger.info(f"Menu reading rate limited (attempt {attempt}); waiting {RETRY_WAIT_SECONDS}s")
                await on_wait(
                    f"The reading model is busy (try {attempt} of {MAX_ATTEMPTS}). Retrying in {RETRY_WAIT_SECONDS} seconds."
                )
                await asyncio.sleep(RETRY_WAIT_SECONDS)
                continue
            raise
    raise RuntimeError("unreachable")


async def extract_menu_items(menu_text: str, on_progress: Optional[ProgressCallback] = None) -> List[Dict[str, Any]]:
    """Returns validated, de-duplicated dishes from the whole menu.

    A chunk the model can't read is skipped and logged. Only a failure on every
    chunk raises, so one bad part of a long menu doesn't lose the rest."""
    text = (menu_text or "").strip()
    if not text:
        return []

    model = _menu_model()
    chunks = chunk_text(text)
    logger.info(f"Menu extraction: {len(chunks)} chunk(s)")

    items: List[Dict[str, Any]] = []
    seen: set = set()
    failures = 0
    last_error: Optional[Exception] = None

    async def report(done: int, note: Optional[str] = None) -> None:
        if on_progress:
            await on_progress(done, len(chunks), note)

    for index, chunk in enumerate(chunks, start=1):
        await report(index - 1)

        async def on_wait(note: str, _done: int = index - 1) -> None:
            await report(_done, note)

        try:
            raw_reply = await _ask_chunk(model, chunk, on_wait)
            parsed = _parse_items(raw_reply)
        except Exception as err:
            failures += 1
            last_error = err
            logger.warning(f"Menu chunk {index}/{len(chunks)} skipped: {err}")
            continue

        for raw in parsed:
            try:
                item = MenuItem(**raw).model_dump()
            except (ValidationError, TypeError) as err:
                logger.info(f"Dropped menu entry {raw!r}: {err}")
                continue
            key = (item["name"].lower(), item["category"].lower())
            if key in seen:
                continue
            seen.add(key)
            items.append(item)
            if len(items) >= MAX_ITEMS:
                await report(len(chunks))
                return items

    await report(len(chunks))
    if failures == len(chunks) and last_error is not None:
        raise last_error
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
