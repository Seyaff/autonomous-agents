"""
The owner's assistant on the settings page. The owner says what to change in plain words. The assistant
makes the change through the same saves the settings screens use, so every change is checked and logged,
then tells the owner what changed.
"""

import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
from pydantic import ValidationError

from core.llm import get_chat_model, is_rate_limit
from core.settings import settings
from core.setup_state import AgentSettings
from services.availability import MENU_ITEMS, today_for
from services.menu_view import menu_text
from services.tenant_settings import (
    TenantUpdatePayload,
    apply_agent_settings,
    apply_tenant_update,
    log_changes,
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are the settings assistant for the owner of {business}. The owner tells you in plain words what to change. You make the change with your tools, then tell them what changed.

Rules:
- Apply clear requests right away with the tools. Don't ask for confirmation for normal settings.
- Call get_restaurant_settings when you need current values before you change something.
- If a request is unclear (for example, which days a time applies to), ask one short question instead of guessing.
- Pausing the customer agent stops replies to every customer. Call set_agent_enabled without confirmed first, and only pass confirmed=true after the owner has clearly said yes.
- Before setting a dish sold out, call list_menu so you use the exact dish name.
- Change only what the owner asked for.
- After making changes, reply with a short list of what changed, as "old -> new".
- Reply in the language the owner writes in (English or Roman Urdu).
- Never invent a setting or a value. If a tool says something wasn't saved, say so."""


def _current_settings(tenant: Dict[str, Any]) -> Dict[str, Any]:
    delivery = tenant.get("delivery_settings") or {}
    return {
        "business_name": tenant.get("business_name"),
        "business_phone": tenant.get("business_phone"),
        "address": tenant.get("address"),
        "currency": tenant.get("currency"),
        "timezone": tenant.get("timezone"),
        "flat_delivery_fee": delivery.get("flat_delivery_fee"),
        "avg_prep_time_minutes": delivery.get("avg_prep_time_minutes"),
        "min_order_amount": tenant.get("min_order_amount"),
        "operating_hours": tenant.get("operating_hours") or [],
        "delivery_areas": tenant.get("delivery_areas") or [],
        "payment_methods": tenant.get("payment_methods") or [],
        "order_types": tenant.get("order_types") or [],
        "reply_settings": tenant.get("agent_settings") or {},
        "agent_enabled": tenant.get("agent_enabled", True),
    }


def _make_tools(db, tenant_id: str, user_id: Any, applied: List[Dict[str, Any]]):
    """The tools close over this turn's tenant and user, so the model can't touch another restaurant."""

    async def _tenant() -> Dict[str, Any]:
        return await db.tenants.find_one({"tenant_id": tenant_id}) or {}

    @tool
    async def get_restaurant_settings() -> dict:
        """Current settings: name, phone, address, currency, timezone, delivery fee, prep time, minimum order,
        opening hours, delivery areas, payment methods, order types, reply settings, and whether the agent is on."""
        return _current_settings(await _tenant())

    @tool
    async def update_restaurant_settings(changes: dict) -> str:
        """Change restaurant settings. Pass only the fields to change. Keys: business_name, business_phone, address,
        currency, timezone, flat_delivery_fee, avg_prep_time_minutes, min_order_amount, operating_hours (all 7 days,
        each {"day": "mon", "open": "12:00", "close": "23:30", "closed": false}), delivery_areas (list of text),
        payment_methods (cash_on_delivery, card_on_delivery, bank_transfer), order_types (delivery, takeaway, dine_in)."""
        unknown = set(changes) - set(TenantUpdatePayload.model_fields)
        if unknown:
            return f"Not saved. Unknown setting: {', '.join(sorted(unknown))}."
        try:
            payload = TenantUpdatePayload(**changes)
        except ValidationError as e:
            return f"Not saved. {e.errors()[0]['msg']}"
        try:
            done = await apply_tenant_update(db, tenant_id, payload, user_id=user_id, source="assistant")
        except ValueError as e:
            return f"Not saved. {e}"
        applied.extend(done)
        return "Saved." if done else "Nothing changed; those values were already set."

    @tool
    async def update_reply_settings(changes: dict) -> str:
        """Change how the agent replies. Keys: language ("match" to follow the customer, "en", or "roman_urdu"),
        tone ("warm", "professional" or "short"), greeting (text, or empty to clear), and escalate_on (an object with
        refund, complaint and human_requested as true/false, and large_order_over as a number or null) for the
        situations that go to the owner."""
        unknown = set(changes) - set(AgentSettings.model_fields)
        if unknown:
            return f"Not saved. Unknown setting: {', '.join(sorted(unknown))}."
        current = (await _tenant()).get("agent_settings") or {}
        merged = {**current, **changes}
        if "escalate_on" in changes:
            merged["escalate_on"] = {**(current.get("escalate_on") or {}), **(changes["escalate_on"] or {})}
        try:
            new_settings = AgentSettings(**merged)
        except ValidationError as e:
            return f"Not saved. {e.errors()[0]['msg']}"
        done = await apply_agent_settings(db, tenant_id, new_settings, user_id=user_id, source="assistant")
        applied.extend(done)
        return "Saved." if done else "Nothing changed; those values were already set."

    @tool
    async def set_agent_enabled(enabled: bool, confirmed: bool = False) -> str:
        """Turn the customer agent on or off for every customer. Turning it off stops all replies, so pass
        confirmed=true only after the owner has clearly said yes."""
        now = datetime.now(timezone.utc)
        current = (await _tenant()).get("agent_enabled", True)
        if current == enabled:
            return "Already set."
        if not enabled and not confirmed:
            return ("Not changed. Ask the owner to confirm they want the agent paused for all customers, "
                    "then call this again with confirmed=true.")
        await db.tenants.update_one({"tenant_id": tenant_id}, {"$set": {"agent_enabled": enabled, "updated_at": now}})
        change = {"field": "agent_enabled", "before": current, "after": enabled}
        await log_changes(db, tenant_id, user_id, "assistant", [change], now)
        applied.append(change)
        return "The agent is on again." if enabled else "The agent is paused for all customers."

    @tool
    async def list_menu(category: str = "") -> str:
        """The dish list grouped by category, with prices and what's sold out today. Use it to match the owner's
        words to exact dish names. Pass a category name to narrow it."""
        return await menu_text(db, await _tenant(), category or None) or "There is no dish list yet."

    @tool
    async def set_dish_sold_out(name: str, sold_out: bool) -> str:
        """Mark a dish sold out for today, or back on the menu. Use the exact dish name from list_menu."""
        now = datetime.now(timezone.utc)
        name = (name or "").strip()
        if not name:
            return "Not saved. Name the dish."
        tenant = await _tenant()
        match = {"tenant_id": tenant_id, "name": {"$regex": f"^{re.escape(name)}$", "$options": "i"}}
        update = {"$set": {"sold_out_on": today_for(tenant)}} if sold_out else {"$unset": {"sold_out_on": ""}}
        result = await db[MENU_ITEMS].update_many(match, update)
        if result.matched_count == 0:
            return f"No dish named {name} on the menu. Check the spelling with list_menu."
        change = {"field": "menu.sold_out", "before": None, "after": name if sold_out else None}
        await log_changes(db, tenant_id, user_id, "assistant", [change], now)
        applied.append(change)
        return f"{name} is sold out today." if sold_out else f"{name} is back on the menu."

    return [get_restaurant_settings, update_restaurant_settings, update_reply_settings, set_agent_enabled, list_menu, set_dish_sold_out]


def _agent(provider: str, tools: List[Any]):
    model = get_chat_model(purpose="owner_assistant", temperature=0.1, provider=provider)
    return create_react_agent(model=model, tools=tools)


def _last_reply(messages: List[BaseMessage]) -> str:
    for msg in reversed(messages):
        if not isinstance(msg, AIMessage) or not msg.content:
            continue
        if isinstance(msg.content, str):
            return msg.content.strip()
        text = "".join(part.get("text", "") for part in msg.content if isinstance(part, dict))
        if text.strip():
            return text.strip()
    return ""


async def run_owner_turn(db, tenant_id: str, user_id: Any, message: str, history: List[Dict[str, str]]) -> Dict[str, Any]:
    """One turn of the owner's chat. Returns the reply and the list of changes that were saved."""
    tenant = await db.tenants.find_one({"tenant_id": tenant_id}) or {}
    applied: List[Dict[str, Any]] = []
    tools = _make_tools(db, tenant_id, user_id, applied)

    messages: List[BaseMessage] = [SystemMessage(content=SYSTEM_PROMPT.format(business=tenant.get("business_name") or "the restaurant"))]
    for turn in history[-20:]:
        cls = HumanMessage if turn["role"] == "owner" else AIMessage
        messages.append(cls(content=turn["content"]))
    messages.append(HumanMessage(content=message))

    primary = settings.LLM_PROVIDER.lower()
    fallback = (settings.LLM_FALLBACK_PROVIDER or "").lower()
    try:
        try:
            result = await _agent(primary, tools).ainvoke({"messages": messages})
        except Exception as e:
            if not fallback or fallback == primary or not is_rate_limit(e):
                raise
            logger.warning(f"[owner-assistant] {primary} is rate-limited; retrying this turn on {fallback}: {type(e).__name__}")
            result = await _agent(fallback, tools).ainvoke({"messages": messages})
    except Exception as e:
        logger.exception(f"[owner-assistant] turn failed for {tenant_id}: {e}")
        return {"reply": "Sorry, I couldn't do that just now. Please try again in a moment.", "changes": applied}

    reply = _last_reply(result.get("messages", [])) or "Done."
    return {"reply": reply, "changes": applied}
