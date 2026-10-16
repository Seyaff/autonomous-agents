"""
The owner's agent: one text box that runs the business. The owner asks a question or says what to change, in plain
words. The agent reads and changes things with the tools in services.assistant_tools, which go through the same
services as the dashboard screens, so every change is checked and logged.

Replies stream to the panel as events: text tokens, each tool step as it starts and ends, saved changes, actions
waiting for the owner's Confirm, and pages to open.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langgraph.prebuilt import create_react_agent

from core.llm import get_chat_model, is_rate_limit
from core.settings import settings
from services.assistant_tools import ACTIONS, Turn, decide_action, make_tools
from services.order_service import tenant_timezone

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are the operator agent inside the dashboard of {business}. The owner types to you in plain words, and you run
the business for them with your tools: answer questions with real numbers, change settings and the catalog, move orders on,
look into customer chats, and prepare messages, templates and campaigns.

Right now it is {now} for the business. Prices are in {currency}.
What the business does: {description}

How to work:
- Use the tools for every fact. Never guess a number, a name, an order or what a customer said. If the tools don't have it, say so.
- Do clear requests right away. Several steps in one request are fine: do them all, in order.
- Read before you change: look up the item, order or chat first so you use exact names and ids.
- If a request could mean two different things, ask one short question instead of guessing.
- Some tools only prepare an action and show the owner a Confirm button: messages to customers, campaigns, new templates,
  forms, cancelling orders, deleting items and pausing the agent. Say in one sentence what will happen when they press it.
  Never say it is done before they confirm.
- The business description is what the customer agent works from. When the owner tells you something lasting about the business
  (what it sells, prices policy, how it works), offer to add it to the description.
- Only call open_page when the owner asks to see or go to something.
- Change only what the owner asked for.

How to reply:
- Short and direct, like a sharp colleague. Lead with the answer.
- Plain text. Use "- " lists for several items and keep each line short. No tables or headings.
- After changes, list them as "old -> new".
- Reply in the language the owner writes in (English or Roman Urdu).
- If a tool says something wasn't saved or failed, say so plainly."""

TRANSCRIPT = "assistant_messages"
HISTORY_TURNS = 20
APOLOGY = "Sorry, I couldn't do that just now. Please try again in a moment."


def _make_tools(db, tenant_id: str, user_id: Any, applied: List[Dict[str, Any]]):
    """The tools for one turn, recording saved changes in applied."""
    return make_tools(db, tenant_id, user_id, Turn(applied=applied))


def _agent(provider: str, tools: List[Any]):
    model = get_chat_model(purpose="owner_assistant", temperature=0.1, provider=provider)
    return create_react_agent(model=model, tools=tools)


def system_prompt(tenant: Dict[str, Any], now: Optional[datetime] = None) -> str:
    now = now or datetime.now(timezone.utc)
    try:
        local = now.astimezone(ZoneInfo(tenant_timezone(tenant)))
    except Exception:
        local = now
    description = (tenant.get("business_description") or "").strip() or "Not written yet."
    if len(description) > 600:
        description = description[:597] + "..."
    return SYSTEM_PROMPT.format(
        business=tenant.get("business_name") or "the business",
        now=local.strftime("%A %d %B %Y, %I:%M %p"),
        currency=tenant.get("currency") or "the local currency",
        description=description,
    )


# ---------------------------------------------------------------------------
# The saved conversation
# ---------------------------------------------------------------------------
async def load_transcript(db, tenant_id: str, user_id: Any, limit: int = 50) -> List[Dict[str, Any]]:
    """The saved conversation for this owner, oldest first. Actions carry their latest status."""
    rows = await db[TRANSCRIPT].find(
        {"tenant_id": tenant_id, "user_id": user_id},
        {"_id": 0, "role": 1, "content": 1, "changes": 1, "actions": 1, "at": 1},
    # _id breaks ties between turns saved within the same clock tick, so they keep the order they were said in.
    ).sort([("at", -1), ("_id", -1)]).to_list(length=limit)
    rows.reverse()
    ids = [a["action_id"] for r in rows for a in r.get("actions") or []]
    if ids:
        latest = {
            a["action_id"]: a
            for a in await db[ACTIONS].find({"tenant_id": tenant_id, "action_id": {"$in": ids}}).to_list(length=len(ids))
        }
        for r in rows:
            for a in r.get("actions") or []:
                saved = latest.get(a["action_id"]) or {}
                a["status"] = saved.get("status", a.get("status"))
                if saved.get("result"):
                    a["result"] = saved["result"]
    return rows


async def save_turn(db, tenant_id: str, user_id: Any, role: str, content: str,
                    changes: Optional[List[Dict[str, Any]]] = None,
                    actions: Optional[List[Dict[str, Any]]] = None) -> None:
    await db[TRANSCRIPT].insert_one({
        "tenant_id": tenant_id,
        "user_id": user_id,
        "role": role,
        "content": content,
        "changes": changes or [],
        "actions": actions or [],
        "at": datetime.now(timezone.utc),
    })


async def clear_transcript(db, tenant_id: str, user_id: Any) -> None:
    await db[TRANSCRIPT].delete_many({"tenant_id": tenant_id, "user_id": user_id})


async def decide(db, tenant_id: str, user_id: Any, action_id: str, confirm: bool) -> Dict[str, Any]:
    """The owner pressed Confirm or Cancel on an action card. The result is added to the conversation,
    so the agent knows about it on the next turn."""
    outcome = await decide_action(db, tenant_id, user_id, action_id, confirm)
    if outcome["status"] in ("done", "failed", "cancelled", "expired"):
        await save_turn(db, tenant_id, user_id, "assistant", outcome["message"], changes=outcome["changes"])
    return outcome


# ---------------------------------------------------------------------------
# One streamed turn
# ---------------------------------------------------------------------------
def _text_of(chunk: Any) -> str:
    content = getattr(chunk, "content", "")
    if isinstance(content, str):
        return content
    return "".join(part.get("text", "") for part in content if isinstance(part, dict) and part.get("type", "text") == "text")


def _build_messages(tenant: Dict[str, Any], prior: List[Dict[str, Any]], message: str) -> List[BaseMessage]:
    messages: List[BaseMessage] = [SystemMessage(content=system_prompt(tenant))]
    for turn in prior:
        content = turn["content"]
        pending = [a for a in turn.get("actions") or [] if a.get("status") == "pending"]
        if pending:
            content += "\n(Still waiting for the owner to confirm: " + "; ".join(a["summary"] for a in pending) + ")"
        cls = HumanMessage if turn["role"] == "owner" else AIMessage
        messages.append(cls(content=content))
    messages.append(HumanMessage(content=message))
    return messages


async def stream_owner_turn(db, tenant_id: str, user_id: Any, message: str):
    """Runs one turn and yields events as they happen. Each event is a dict with a "type":
    token (text), tool (a step started: id, name), tool_end (id, name), change (a saved change),
    confirm (an action waiting for the owner), navigate (href), error, and finally done (reply).
    The turn and its reply are saved when it finishes."""
    tenant = await db.tenants.find_one({"tenant_id": tenant_id}) or {}
    history = await load_transcript(db, tenant_id, user_id, limit=HISTORY_TURNS)
    await save_turn(db, tenant_id, user_id, "owner", message)

    turn = Turn()
    tools = make_tools(db, tenant_id, user_id, turn)
    messages = _build_messages(tenant, history, message)
    providers = [settings.LLM_PROVIDER.lower()]
    fallback = (settings.LLM_FALLBACK_PROVIDER or "").lower()
    if fallback and fallback != providers[0]:
        providers.append(fallback)

    reply_parts: List[str] = []
    sent = {"change": 0, "confirm": 0, "navigate": 0}

    def pending_events():
        for kind, items, key in (("change", turn.applied, "change"), ("confirm", turn.actions, "action"), ("navigate", turn.pages, "href")):
            while sent[kind] < len(items):
                yield {"type": kind, key: items[sent[kind]]}
                sent[kind] += 1

    failed = False
    for index, provider in enumerate(providers):
        started = False
        try:
            async for event in _agent(provider, tools).astream_events({"messages": messages}, version="v2"):
                kind = event["event"]
                if kind == "on_chat_model_stream":
                    text = _text_of(event["data"]["chunk"])
                    if text:
                        started = True
                        reply_parts.append(text)
                        yield {"type": "token", "text": text}
                elif kind == "on_tool_start":
                    started = True
                    yield {"type": "tool", "name": event["name"], "id": event.get("run_id") or event["name"]}
                elif kind == "on_tool_end":
                    yield {"type": "tool_end", "name": event["name"], "id": event.get("run_id") or event["name"]}
                elif kind == "on_chat_model_start" and reply_parts:
                    # A new model call after tools: keep its text apart from what came before.
                    reply_parts.append("\n\n")
                    yield {"type": "token", "text": "\n\n"}
                for out in pending_events():
                    yield out
            break
        except Exception as e:
            can_retry = not started and index + 1 < len(providers) and is_rate_limit(e)
            if can_retry:
                logger.warning(f"[owner-assistant] {provider} is rate-limited; retrying this turn on {providers[index + 1]}")
                continue
            logger.exception(f"[owner-assistant] turn failed for {tenant_id}: {e}")
            failed = True
            break

    for out in pending_events():
        yield out
    if failed:
        reply_parts = [APOLOGY]
        yield {"type": "error", "message": APOLOGY}
    reply = "".join(reply_parts).strip() or ("Waiting for your go-ahead." if turn.actions else "Done.")
    await save_turn(db, tenant_id, user_id, "assistant", reply, changes=turn.applied, actions=turn.actions)
    yield {"type": "done", "reply": reply}
