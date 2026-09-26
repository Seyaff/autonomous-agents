import logging
from typing import Any, Dict, Optional
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
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

# Primary LLM for conversational customer support & tool calls
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


def get_customer_support_agent(db: Any) -> CompiledStateGraph:
    """Returns or compiles the persistent customer support agent backed by MongoDB checkpointer."""
    global _agent_cache
    if "master" not in _agent_cache:
        checkpointer = MongoDBCkptSaver(db)
        # create_react_agent handles tool calling loops, async execution, and checkpoint persistence
        _agent_cache["master"] = create_react_agent(
            model=model,
            tools=tools,
            checkpointer=checkpointer,
        )
    return _agent_cache["master"]


async def run_customer_support_turn(
    db: Any,
    tenant: Dict[str, Any],
    customer_phone: str,
    user_message: str
) -> str:
    """
    Executes a turn of customer support with dynamic prompt compilation,
    long-term memory injection, and persistent MongoDB checkpointing.
    """
    tenant_id = tenant.get("tenant_id", "default_tenant")
    thread_id = f"{tenant_id}:{customer_phone}"

    # 1. Retrieve customer long-term profile / history
    customer_context = await format_customer_context(tenant_id, customer_phone)

    # 2. Compile dynamic system prompt
    system_prompt = compile_customer_support_prompt(tenant, customer_context)

    # 3. Prepare LangGraph execution config
    config = {
        "configurable": {
            "thread_id": thread_id,
            "tenant_id": tenant_id,
            "customer_phone": customer_phone,
        }
    }

    agent = get_customer_support_agent(db)

    # 4. Invoke agent with system prompt and user's inbound WhatsApp message
    input_messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_message),
    ]

    result = await agent.ainvoke({"messages": input_messages}, config=config)

    # 5. Extract latest AI response
    messages = result.get("messages", [])
    reply_text = ""
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and msg.content:
            if isinstance(msg.content, list):
                reply_text = "".join(
                    b.get("text", "") for b in msg.content if isinstance(b, dict)
                )
            else:
                reply_text = str(msg.content)
            if reply_text.strip():
                break

    return reply_text or "Ji, aap ka paigham mosool ho gaya hai. Hum aap ki mazeed kya madad kar sakte hain?"