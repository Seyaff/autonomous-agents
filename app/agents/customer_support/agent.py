import logging
import asyncio
import weakref
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langgraph.prebuilt import create_react_agent
from langgraph.graph.state import CompiledStateGraph

from core.llm import get_chat_model
from memory.context_builder import build_agent_context, remember_exchange
from services.billing import record_agent_reply, tokens_from_messages
from services.availability import sold_out_names
from services.alerts import raise_alert
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

TRACE_SUMMARY_CHARS = 120
ESCALATION_TOOL = "escalate_to_owner"

FALLBACK_REPLY = (
    "Ji, aap ka paigham mosool ho gaya hai. "
    "Hum aap ki mazeed kya madad kar sakte hain?"
)
ERROR_REPLY = (
    "Maazrat, abhi technical masla aa gaya hai. "
    "Thori dair baad dobara koshish karein."
)


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
# Per-conversation locks, so two quick messages from one customer are answered
# in order rather than racing each other. Self-cleaning.
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
    history is rebuilt from stored data every turn, so nothing is stored twice."""
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


def build_trace(messages: List[BaseMessage]) -> List[Dict[str, Any]]:
    """Each tool call the agent made this turn, paired with its result."""
    results = {m.tool_call_id: m.content for m in messages if isinstance(m, ToolMessage)}
    trace: List[Dict[str, Any]] = []
    for m in messages:
        if not isinstance(m, AIMessage):
            continue
        for call in m.tool_calls or []:
            content = str(results.get(call.get("id"), ""))
            trace.append({
                "tool": call.get("name", ""),
                "args": call.get("args", {}),
                "result_summary": content[:TRACE_SUMMARY_CHARS],
            })
    return trace


def _escalated(trace: List[Dict[str, Any]]) -> bool:
    return any(
        t["tool"] == ESCALATION_TOOL and not t["result_summary"].startswith("Could not")
        for t in trace
    )


async def run_agent_turn(
    db: Any,
    tenant: Dict[str, Any],
    customer_phone: str,
    user_message: str,
    inbound_wamid: Optional[str] = None,
    test_mode: bool = False,
    test_history: Optional[List[BaseMessage]] = None,
) -> Dict[str, Any]:
    """Answers one message and reports what happened.

    Returns {reply, trace, escalated}. The trace lists each tool call with its result.

    Normal mode builds context from stored data (customer card, recent messages),
    then remembers durable facts after the reply.

    Test mode (the owner's test chat) uses only `test_history` as context. It
    skips memory, usage metering and fact extraction, and the tools change nothing.
    """
    tenant_id = tenant.get("tenant_id", "default_tenant")

    if test_mode:
        conversation_id = None
        customer_context = (
            "TEST CHAT: the owner is testing you. No real customer, no customer memory, "
            "and nothing is saved or sent."
        )
        window = list(test_history or [])
        lock_key = f"test:{tenant_id}:{customer_phone}"
    else:
        conversation = await db["conversations"].find_one(
            {"tenant_id": tenant_id, "customer_phone": customer_phone}, {"conversation_id": 1}
        )
        conversation_id = (conversation or {}).get("conversation_id") or f"conv_{tenant_id}_{customer_phone}"
        context = await build_agent_context(
            db, tenant_id, customer_phone, conversation_id, exclude_wamid=inbound_wamid
        )
        customer_context = context["customer_context"]
        window = context["window"]
        lock_key = f"{tenant_id}:{customer_phone}"

    lock = await _get_thread_lock(lock_key)

    async with lock:
        sold_out = await sold_out_names(db, tenant)
        system_prompt = compile_customer_support_prompt({**tenant, "sold_out": sold_out}, customer_context)
        messages: List[BaseMessage] = [
            SystemMessage(content=system_prompt),
            *window,
            HumanMessage(content=user_message),
        ]

        config = {
            "configurable": {
                "tenant_id": tenant_id,
                "customer_phone": customer_phone,
                "test_mode": test_mode,
            },
            "run_name": f"{'test-chat' if test_mode else 'whatsapp-turn'}-{customer_phone}",
            "tags": [tenant_id, "test" if test_mode else "whatsapp"],
            "metadata": {"tenant_id": tenant_id, "customer_phone": customer_phone},
        }

        try:
            result = await get_customer_support_agent().ainvoke({"messages": messages}, config=config)
        except Exception as e:
            logger.exception(f"Agent invocation failed for {tenant_id}:{customer_phone}: {e}")
            if not test_mode:
                await raise_alert(
                    db,
                    tenant_id,
                    kind="agent_error",
                    title=f"The agent failed on a message from {customer_phone}",
                    detail=f"The customer got an apology. Check the conversation. ({type(e).__name__})",
                    severity="warning",
                    ref={"customer_phone": customer_phone},
                )
            return {"reply": ERROR_REPLY, "trace": [], "escalated": False}

        all_messages = result.get("messages", [])
        new_messages = all_messages[len(messages):]
        reply_text = _extract_latest_ai_text(all_messages) or FALLBACK_REPLY
        trace = build_trace(new_messages)

    if not test_mode:
        await record_agent_reply(
            db,
            tenant_id,
            conversation_id,
            tokens_from_messages(all_messages),
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

    return {"reply": reply_text, "trace": trace, "escalated": _escalated(trace)}


async def run_customer_support_turn(
    db: Any,
    tenant: Dict[str, Any],
    customer_phone: str,
    user_message: str,
    inbound_wamid: str | None = None,
) -> str:
    """WhatsApp entry point: returns only the reply text."""
    turn = await run_agent_turn(
        db, tenant, customer_phone, user_message, inbound_wamid=inbound_wamid
    )
    return turn["reply"]
