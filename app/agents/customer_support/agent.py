import os
from dotenv import load_dotenv
import logging
import asyncio
import weakref
from typing import Any, Dict, List

from langchain_groq import ChatGroq
from langchain_core.messages import (
    SystemMessage,
    HumanMessage,
    AIMessage,
    BaseMessage,
    trim_messages,
)
from langgraph.prebuilt import create_react_agent
from langgraph.graph.state import CompiledStateGraph

from core.settings import settings
from memory.mongo_checkpointer import MongoDBCkptSaver
from memory.customer_memory import format_customer_context
from agents.customer_support.prompt import compile_customer_support_prompt
from agents.customer_support.tools import (
    search_uploaded_documents,
    create_order_tool,
    get_order_status_tool,
    update_order_tool,
    cancel_order_tool,
)

logger = logging.getLogger(__name__)

load_dotenv()


# ---------------------------------------------------------------------------
# LLM + Tools
# ---------------------------------------------------------------------------
model = ChatGroq(
    model="openai/gpt-oss-120b",
    temperature=0.1,
    groq_api_key=settings.GROQ_API_KEY,
)

tools = [
    search_uploaded_documents,
    create_order_tool,
    get_order_status_tool,
    update_order_tool,
    cancel_order_tool,
]

_agent_cache: Dict[str, CompiledStateGraph] = {}


# ---------------------------------------------------------------------------
# Per-thread locks (self-cleaning, no unbounded defaultdict)
# ---------------------------------------------------------------------------
_thread_locks: "weakref.WeakValueDictionary[str, asyncio.Lock]" = (
    weakref.WeakValueDictionary()
)
_locks_guard = asyncio.Lock()


async def _get_thread_lock(thread_id: str) -> asyncio.Lock:
    """
    Returns a per-thread asyncio.Lock. Uses a WeakValueDictionary so locks
    that are no longer referenced get garbage-collected automatically — no
    memory growth as new customers come in.
    """
    async with _locks_guard:
        lock = _thread_locks.get(thread_id)
        if lock is None:
            lock = asyncio.Lock()
            _thread_locks[thread_id] = lock
        return lock


# ---------------------------------------------------------------------------
# Token counting (no transformers / tiktoken dependency)
# ---------------------------------------------------------------------------
def count_tokens(messages: List[BaseMessage]) -> int:
    """
    Rough token counter for a list of messages.

    ~3 chars/token, conservative for mixed English + Roman Urdu. Being
    conservative means we trim slightly earlier — good for Groq TPM safety.
    """
    total = 0
    for m in messages:
        content = getattr(m, "content", "")
        if isinstance(content, list):
            content = "".join(b.get("text", "") for b in content if isinstance(b, dict))
        total += len(str(content)) // 3
    return total


trimmer = trim_messages(
    max_tokens=3000,
    strategy="last",
    token_counter=count_tokens,
    start_on="human",
    include_system=False,
)


# ---------------------------------------------------------------------------
# Agent factory (cached per process)
# ---------------------------------------------------------------------------
def get_customer_support_agent(db: Any) -> CompiledStateGraph:
    """Returns or compiles the persistent customer support agent backed by MongoDB checkpointer."""
    if "master" not in _agent_cache:
        checkpointer = MongoDBCkptSaver(db)
        _agent_cache["master"] = create_react_agent(
            model=model,
            tools=tools,
            checkpointer=checkpointer,
        )
    return _agent_cache["master"]


# ---------------------------------------------------------------------------
# Reply extraction helper
# ---------------------------------------------------------------------------
def _extract_latest_ai_text(messages: List[BaseMessage]) -> str:
    """Walks the message list backwards and returns the newest non-empty AI text."""
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


# ---------------------------------------------------------------------------
# Main turn handler
# ---------------------------------------------------------------------------
async def run_customer_support_turn(
    db: Any,
    tenant: Dict[str, Any],
    customer_phone: str,
    user_message: str,
) -> str:
    """
    Executes a turn of customer support with dynamic system prompt,
    message history trimming, and persistent MongoDB checkpointing.

    Concurrent invocations for the same (tenant, customer) are serialized via
    a per-thread asyncio.Lock so webhook retries can't interleave state.
    """
    tenant_id = tenant.get("tenant_id", "default_tenant")
    thread_id = f"{tenant_id}:{customer_phone}"

    lock = await _get_thread_lock(thread_id)

    async with lock:
        # 1. Long-term customer context
        customer_context = await format_customer_context(tenant_id, customer_phone)

        # 2. Dynamic system prompt
        system_prompt = compile_customer_support_prompt(tenant, customer_context)

        # 3. LangGraph config
        config = {
            "configurable": {
                "thread_id": thread_id,
                "tenant_id": tenant_id,
                "customer_phone": customer_phone,
            },
            "run_name": f"whatsapp-turn-{customer_phone}",
            "tags": [tenant_id, "whatsapp", "production"],
            "metadata": {
                "tenant_id": tenant_id,
                "customer_phone": customer_phone,
                "thread_id": thread_id,
            },
        }

        agent = get_customer_support_agent(db)

        # 4. Load current checkpoint
        current_state = await agent.aget_state(config)
        existing_messages: List[BaseMessage] = (
            current_state.values.get("messages", []) if current_state else []
        )

        # 5. Drop stale SystemMessages (they're rebuilt every turn)
        clean_history = [
            m for m in existing_messages if not isinstance(m, SystemMessage)
        ]

        # 6. Trim history — guard against empty input
        if clean_history:
            try:
                trimmed_history = trimmer.invoke(clean_history)
            except Exception as e:
                logger.warning(
                    f"Trimmer failed for {thread_id}, falling back to last 10: {e}"
                )
                trimmed_history = clean_history[-10:]
        else:
            trimmed_history = []

        # 7. Fresh system prompt + trimmed history + new user message
        exec_messages: List[BaseMessage] = (
            [SystemMessage(content=system_prompt)]
            + trimmed_history
            + [HumanMessage(content=user_message)]
        )

        print(f"Messages : {exec_messages}")
        # 8. Invoke agent
        try:
            result = await agent.ainvoke({"messages": exec_messages}, config=config)
        except Exception as e:
            logger.exception(f"Agent invocation failed for thread {thread_id}: {e}")
            return (
                "Maazrat, abhi technical masla aa gaya hai. "
                "Thori dair baad dobara koshish karein."
            )

        # 9. Extract reply
        reply_text = _extract_latest_ai_text(result.get("messages", []))

        return reply_text or (
            "Ji, aap ka paigham mosool ho gaya hai. "
            "Hum aap ki mazeed kya madad kar sakte hain?"
        )
