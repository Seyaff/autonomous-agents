"""
Pulls durable customer facts out of one exchange (customer message + agent reply).

Runs on a small model after each customer message, so it stays cheap. It only
proposes changes. Anything that fails validation is dropped and logged, so a
bad model reply can never corrupt the customer's record.
"""

import json
import logging
import re
from typing import Any, Dict, List

from pydantic import ValidationError
from langchain_core.messages import HumanMessage, SystemMessage

from core.llm import get_chat_model
from core.settings import settings
from memory.facts import FACT_KINDS, FactChange

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """You maintain a memory of one restaurant customer for the restaurant's WhatsApp agent.

Read the latest exchange and decide what, if anything, is worth remembering about THIS customer for future conversations.

Remember only durable facts about the customer:
- preference: how they like things (spice level, portion size, usual time, drink choice)
- dietary / allergy: restrictions and allergies (always important)
- address: a delivery place they use (Gulberg III, office on Main Blvd)
- complaint: a problem they had that the restaurant should know about
- note: anything else that would help the next conversation
- service: standing requests (no call before 9pm, ring the bell twice)

Do NOT remember:
- order details that are already recorded (items bought, favourite dishes, totals, order IDs, how often they order)
- one-off messages ("ok", "thanks", "what time do you open today")
- anything about other people, or anything you are unsure of
- anything the restaurant said, unless the customer confirmed it as their own preference

Write "value" as one short, complete sentence about the customer, e.g. "Wants extra spicy food" or "Allergic to peanuts". Use the same key for the same topic.

Facts already remembered (use the same key to update one, or action "forget" to remove one):
{existing}

Latest exchange:
Customer: {customer}
Agent: {agent}

Reply with JSON only, in this shape:
{{"changes": [{{"action": "set" or "forget", "kind": one of {kinds}, "key": short_snake_case_name, "value": "short description", "confidence": 0.0-1.0}}]}}
If nothing is worth remembering, reply {{"changes": []}}."""


def _memory_model():
    if (settings.LLM_PROVIDER or "groq").lower() == "openai":
        return get_chat_model(purpose="memory_extractor", temperature=0.0, model=settings.MEMORY_OPENAI_MODEL)
    return get_chat_model(purpose="memory_extractor", temperature=0.0, model=settings.MEMORY_GROQ_MODEL)


def _parse_json(text: str) -> Dict[str, Any]:
    """Parses the first JSON object in the reply, tolerating fences and extra prose."""
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object in reply")
    return json.loads(text[start:end + 1])


def _format_existing(facts: List[Dict[str, Any]]) -> str:
    if not facts:
        return "(none yet)"
    return "\n".join(f"- {f['kind']} / {f['key']}: {f['value']}" for f in facts)


async def extract_fact_changes(
    existing_facts: List[Dict[str, Any]],
    customer_text: str,
    agent_text: str,
) -> List[FactChange]:
    """Returns validated changes. Never raises: on any failure it returns []."""
    if not customer_text.strip():
        return []

    prompt = EXTRACTION_PROMPT.format(
        existing=_format_existing(existing_facts),
        customer=customer_text[:1500],
        agent=(agent_text or "")[:1500],
        kinds=", ".join(FACT_KINDS),
    )

    try:
        response = await _memory_model().ainvoke([
            SystemMessage(content="You output strict JSON for a memory system."),
            HumanMessage(content=prompt),
        ])
        data = _parse_json(str(response.content))
    except Exception as e:
        logger.warning(f"Memory extraction failed to produce usable JSON: {e}")
        return []

    changes: List[FactChange] = []
    for raw in data.get("changes", []) if isinstance(data, dict) else []:
        try:
            changes.append(FactChange(**raw))
        except (ValidationError, TypeError) as e:
            logger.info(f"Dropped invalid memory change {raw!r}: {e}")
    return changes
