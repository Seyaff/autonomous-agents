"""
Builds what the agent sees on each turn.

Memory has two parts, both stored once and read fresh every turn:
- the customer card (orders, favourites, durable facts), see customer_card.py
- the recent window: the last few messages of this conversation, read from
  the `messages` collection, which also holds what the restaurant staff said

Nothing here is replayed back into storage, so the stored record never grows
with duplicates however many turns happen.
"""

import logging
from typing import Any, Dict, List, Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from memory.customer_card import build_customer_card, render_card
from memory.facts import apply_fact_changes
from memory.extractor import extract_fact_changes

logger = logging.getLogger(__name__)

WINDOW_MESSAGES = 12
WINDOW_CHAR_BUDGET = 4000  # roughly 1,000 tokens; oldest messages drop first


def _to_message(doc: Dict[str, Any]) -> Optional[BaseMessage]:
    content = (doc.get("content") or "").strip()
    if not content:
        return None
    sender = doc.get("sender")
    if sender == "customer":
        return HumanMessage(content=content)
    if sender == "human":
        return AIMessage(content=f"[restaurant staff] {content}")
    if sender == "system":
        return AIMessage(content=f"[system notice] {content}")
    return AIMessage(content=content)


async def build_recent_window(
    db,
    conversation_id: str,
    exclude_wamid: Optional[str] = None,
) -> List[BaseMessage]:
    """Last WINDOW_MESSAGES messages in time order, skipping the inbound one
    that triggered this turn (it is added separately)."""
    query: Dict[str, Any] = {"conversation_id": conversation_id}
    if exclude_wamid:
        query["wamid"] = {"$ne": exclude_wamid}

    docs = await db["messages"].find(
        query, {"content": 1, "sender": 1, "created_at": 1}
    ).sort("created_at", -1).limit(WINDOW_MESSAGES).to_list(length=WINDOW_MESSAGES)

    messages = [m for m in (_to_message(d) for d in reversed(docs)) if m is not None]

    # Enforce the character budget from the oldest end.
    total = 0
    kept: List[BaseMessage] = []
    for m in reversed(messages):
        total += len(str(m.content))
        if total > WINDOW_CHAR_BUDGET:
            break
        kept.append(m)
    return list(reversed(kept))


async def build_agent_context(
    db,
    tenant_id: str,
    customer_phone: str,
    conversation_id: str,
    exclude_wamid: Optional[str] = None,
) -> Dict[str, Any]:
    card = await build_customer_card(db, tenant_id, customer_phone)
    window = await build_recent_window(db, conversation_id, exclude_wamid)
    return {
        "customer_context": render_card(card),
        "card": card,
        "window": window,
    }


async def remember_exchange(
    db,
    tenant_id: str,
    customer_phone: str,
    customer_text: str,
    agent_text: str,
    source_wamid: Optional[str],
) -> int:
    """Extracts durable facts from one exchange and stores them. Returns the number written.
    Runs in the background after the reply is sent, and never raises."""
    try:
        from memory.facts import list_active_facts

        existing = await list_active_facts(db, tenant_id, customer_phone, limit=30)
        changes = await extract_fact_changes(existing, customer_text, agent_text)
        if not changes:
            return 0
        return await apply_fact_changes(
            db,
            tenant_id,
            customer_phone,
            changes,
            source={"type": "chat", "wamid": source_wamid},
        )
    except Exception as e:
        logger.warning(f"Remembering exchange failed for {customer_phone}: {e}")
        return 0
