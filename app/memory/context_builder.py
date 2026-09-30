import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage
from langchain_core.messages.utils import trim_messages

from core.database import get_database
from core.settings import settings
from memory.customer_memory import format_customer_context
from memory.models import ConversationSummary, AgentContext
from agents.customer_support.prompt import compile_customer_support_prompt

logger = logging.getLogger(__name__)

MAX_RECENT_TURNS = 6
MAX_RECENT_TOKENS = 1500


def count_tokens(messages: List[BaseMessage]) -> int:
    total = 0
    for m in messages:
        content = getattr(m, "content", "")
        if isinstance(content, list):
            content = "".join(b.get("text", "") for b in content if isinstance(b, dict))
        total += len(str(content)) // 3
    return total


def trim_recent_messages(messages: List[BaseMessage], max_turns: int = MAX_RECENT_TURNS) -> List[BaseMessage]:
    user_messages = [m for m in messages if isinstance(m, HumanMessage)]
    if len(user_messages) <= max_turns:
        return messages

    keep_from = len(messages) - (max_turns * 2)
    return messages[max(0, keep_from):]


async def build_agent_context(
    tenant: Dict[str, Any],
    customer_phone: str,
    thread_id: str,
    db=None,
) -> AgentContext:
    if db is None:
        db = get_database()

    tenant_id = tenant.get("tenant_id", "default_tenant")

    profile = await db["customer_profiles"].find_one(
        {"tenant_id": tenant_id, "customer_phone": customer_phone}
    )
    customer_profile = profile if profile else None

    summary = await get_latest_summary(tenant_id, customer_phone)

    config = {
        "configurable": {
            "thread_id": thread_id,
            "tenant_id": tenant_id,
            "customer_phone": customer_phone,
        }
    }

    from agents.customer_support.agent import get_customer_support_agent
    agent = get_customer_support_agent(db)
    state = await agent.aget_state(config)
    existing_messages: List[BaseMessage] = state.values.get("messages", []) if state else []

    clean_history = [m for m in existing_messages if not isinstance(m, SystemMessage)]

    recent_messages = trim_recent_messages(clean_history, MAX_RECENT_TURNS)

    customer_context = format_customer_context(tenant_id, customer_phone)
    system_prompt = compile_customer_support_prompt(tenant, customer_context)

    if summary:
        summary_injection = f"""

=== CONVERSATION SUMMARY (Previous Context) ===
{summary.summary}

Key Entities: {summary.key_entities}
Topics: {', '.join(summary.topics) if summary.topics else 'None'}
Sentiment: {summary.sentiment}
Decisions: {'; '.join(summary.decisions) if summary.decisions else 'None'}
=== END SUMMARY ===
"""
        system_prompt += summary_injection

    recent_messages_dict = []
    for m in recent_messages:
        if isinstance(m, HumanMessage):
            recent_messages_dict.append({"role": "user", "content": m.content})
        elif isinstance(m, AIMessage):
            recent_messages_dict.append({"role": "assistant", "content": m.content})

    return AgentContext(
        system_prompt=system_prompt,
        recent_messages=recent_messages_dict,
        customer_profile=customer_profile,
        conversation_summary=summary,
    )


async def get_latest_summary(tenant_id: str, customer_phone: str) -> Optional[ConversationSummary]:
    db = get_database()
    doc = await db["conversation_summaries"].find_one(
        {"tenant_id": tenant_id, "customer_phone": customer_phone},
        sort=[("created_at", -1)],
    )
    if doc:
        doc.pop("_id", None)
        return ConversationSummary(**doc)
    return None


async def trigger_summarization_if_needed(
    tenant_id: str,
    customer_phone: str,
    thread_id: str,
) -> None:
    from memory.summarizer import summarizer

    try:
        trigger = await summarizer.should_summarize(thread_id, tenant_id, customer_phone)
        if trigger.should_summarize:
            logger.info(f"Triggering summarization for {thread_id}: {trigger.reason}")

            config = {
                "configurable": {
                    "thread_id": thread_id,
                    "tenant_id": tenant_id,
                    "customer_phone": customer_phone,
                }
            }

            from agents.customer_support.agent import get_customer_support_agent
            db = get_database()
            agent = get_customer_support_agent(db)
            state = await agent.aget_state(config)
            messages = state.values.get("messages", []) if state else []

            summary = await summarizer.generate_summary(
                messages, tenant_id, customer_phone, thread_id
            )
            await summarizer.save_summary(summary)
            logger.info(f"Saved summary for {thread_id}")
    except Exception as e:
        logger.warning(f"Summarization check failed for {thread_id}: {e}")