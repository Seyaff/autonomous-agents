import logging
import asyncio
import weakref
from typing import Any, Dict, List

from dotenv import load_dotenv
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
)
from langgraph.prebuilt import create_react_agent
from langgraph.graph.state import CompiledStateGraph

from core.llm import get_chat_model
from memory.context_builder import build_agent_context, remember_exchange
from services.billing import record_agent_reply, tokens_from_messages
from agents.customer_support.prompt import compile_customer_support_prompt
from agents.customer_support.tools import (
    search_uploaded_documents,
    create_order_tool,
    get_order_status_tool,
    update_order_tool,
    cancel_order_tool,
    escalate_to_owner,
)

logger = logging.getLogger(__name__)

load_dotenv()


# ---------------------------------------------------------------------------
# LLM + Tools
# ---------------------------------------------------------------------------
model = get_chat_model(purpose="customer_support", temperature=0.1)

tools = [
    search_uploaded_documents,
    create_order_tool,
    get_order_status_tool,
    update_order_tool,
    cancel_order_tool,
    escalate_to_owner,
]

_agent: CompiledStateGraph | None = None


# ---------------------------------------------------------------------------
# Per-customer locks, so two quick messages from one customer are answered in
# order rather than racing each other. Self-cleaning.
# ---------------------------------------------------------------------------
_thread_locks: "weakref.WeakValueDictionary[str, asyncio.Lock]" = (
    weakref.WeakValueDictionary()
)
_locks_guard = asyncio.Lock()


async def _get_thread_lock(key: str) -> asyncio.Lock:
    async with _locks_guard:
        lock = _thread_locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            _thread_locks[key] = lock
        return lock


def get_customer_support_agent() -> CompiledStateGraph:
    """One compiled agent for the process. It has no checkpointer on purpose:
    history is rebuilt from the messages collection every turn, so nothing is
    stored twice and the staff's replies are always visible to it."""
    global _agent
    if _agent is None:
        _agent = create_react_agent(model=model, tools=tools)
    return _agent


def _extract_latest_ai_text(messages: List[BaseMessage]) -> str:
    for msg in reversed(messages):
        if not isinstance(msg, AIMessage) or not msg.content:
            continue
        if isinstance(msg.content, list):
            text = "".join(
                b.get("text", "") for b in msg.content if isinstance(b, dict)
            )
        else:
            text = str(msg.content)
        if text.strip():
            return text
    return ""


async def run_customer_support_turn(
    db: Any,
    tenant: Dict[str, Any],
    customer_phone: str,
    user_message: str,
    inbound_wamid: str | None = None,
) -> str:
    """Answers one customer message.

    Each turn is built from stored data: the customer card (orders, favourites,
    durable facts) and the recent window of this conversation. After the reply,
    durable facts from the exchange are remembered in the background.
    """
    tenant_id = tenant.get("tenant_id", "default_tenant")
    conversation = await db["conversations"].find_one(
        {"tenant_id": tenant_id, "customer_phone": customer_phone}, {"conversation_id": 1}
    )
    conversation_id = (conversation or {}).get("conversation_id") or f"conv_{tenant_id}_{customer_phone}"

    lock = await _get_thread_lock(f"{tenant_id}:{customer_phone}")

    async with lock:
        context = await build_agent_context(
            db, tenant_id, customer_phone, conversation_id, exclude_wamid=inbound_wamid
        )

        system_prompt = compile_customer_support_prompt(tenant, context["customer_context"])
        messages: List[BaseMessage] = [
            SystemMessage(content=system_prompt),
            *context["window"],
            HumanMessage(content=user_message),
        ]

        config = {
            "configurable": {
                "tenant_id": tenant_id,
                "customer_phone": customer_phone,
            },
            "run_name": f"whatsapp-turn-{customer_phone}",
            "tags": [tenant_id, "whatsapp", "production"],
            "metadata": {"tenant_id": tenant_id, "customer_phone": customer_phone},
        }

        try:
            result = await get_customer_support_agent().ainvoke({"messages": messages}, config=config)
        except Exception as e:
            logger.exception(f"Agent invocation failed for {tenant_id}:{customer_phone}: {e}")
            return (
                "Maazrat, abhi technical masla aa gaya hai. "
                "Thori dair baad dobara koshish karein."
            )

        reply_text = _extract_latest_ai_text(result.get("messages", []))
        await record_agent_reply(
            db,
            tenant_id,
            conversation_id,
            tokens_from_messages(result.get("messages", [])),
        )

    asyncio.create_task(
        remember_exchange(
            db,
            tenant_id,
            customer_phone,
            customer_text=user_message,
            agent_text=reply_text,
            source_wamid=inbound_wamid,
        )
    )

    return reply_text or (
        "Ji, aap ka paigham mosool ho gaya hai. "
        "Hum aap ki mazeed kya madad kar sakte hain?"
    )
