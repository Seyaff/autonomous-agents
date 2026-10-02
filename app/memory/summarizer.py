import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage

from core.llm import get_chat_model
from core.database import get_database
from memory.models import ConversationSummary, SummarizationTrigger

logger = logging.getLogger(__name__)

SUMMARIZATION_PROMPT = """You are a conversation summarizer for a restaurant WhatsApp agent.
Summarize the following conversation between a customer and the restaurant AI agent.

Extract:
1. A concise summary (2-3 sentences)
2. Key entities mentioned (customer name, items discussed, order IDs, addresses, preferences)
3. Main topics discussed
4. Overall sentiment (positive/negative/neutral)
5. Any decisions made or actions taken

Conversation:
{messages}

Return as JSON with keys: summary, key_entities, topics, sentiment, decisions"""


class ConversationSummarizer:
    def __init__(self):
        self.llm = get_chat_model(purpose="summarizer", temperature=0.1)
        self.db = None
        self.SUMMARIZE_EVERY_N_TURNS = 6
        self.MAX_TOKENS_BEFORE_SUMMARY = 3000

    def _get_db(self):
        if self.db is None:
            self.db = get_database()
        return self.db

    def estimate_tokens(self, messages: List[BaseMessage]) -> int:
        total = 0
        for m in messages:
            content = getattr(m, "content", "")
            if isinstance(content, list):
                content = "".join(b.get("text", "") for b in content if isinstance(b, dict))
            total += len(str(content)) // 3
        return total

    def format_messages_for_summary(self, messages: List[BaseMessage]) -> str:
        formatted = []
        for m in messages:
            if isinstance(m, HumanMessage):
                formatted.append(f"Customer: {m.content}")
            elif isinstance(m, AIMessage):
                formatted.append(f"Agent: {m.content}")
        return "\n".join(formatted)

    async def should_summarize(
        self, thread_id: str, tenant_id: str, customer_phone: str
    ) -> SummarizationTrigger:
        db = self._get_db()

        existing = await db["conversation_summaries"].find_one(
            {"thread_id": thread_id}, sort=[("created_at", -1)]
        )

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
        messages = state.values.get("messages", []) if state else []

        user_messages = [m for m in messages if isinstance(m, HumanMessage)]
        turn_count = len(user_messages)

        if existing:
            last_summary_at = existing.get("created_at", datetime.now(timezone.utc))
            messages_since_summary = [
                m for m in user_messages
                if hasattr(m, "timestamp") and m.timestamp > last_summary_at
            ]
            recent_turns = len(messages_since_summary)
        else:
            recent_turns = turn_count

        token_estimate = self.estimate_tokens(messages)

        should_summarize = (
            recent_turns >= self.SUMMARIZE_EVERY_N_TURNS
            or token_estimate > self.MAX_TOKENS_BEFORE_SUMMARY
        )

        reason = ""
        if recent_turns >= self.SUMMARIZE_EVERY_N_TURNS:
            reason = f"Turn threshold reached: {recent_turns} turns since last summary"
        elif token_estimate > self.MAX_TOKENS_BEFORE_SUMMARY:
            reason = f"Token threshold exceeded: ~{token_estimate} tokens"

        return SummarizationTrigger(
            should_summarize=should_summarize,
            reason=reason,
            turn_count=turn_count,
            token_estimate=token_estimate,
        )

    async def generate_summary(
        self, messages: List[BaseMessage], tenant_id: str, customer_phone: str, thread_id: str
    ) -> ConversationSummary:
        if not messages:
            return ConversationSummary(
                tenant_id=tenant_id,
                customer_phone=customer_phone,
                thread_id=thread_id,
                summary="No conversation history",
            )

        user_messages = [m for m in messages if isinstance(m, HumanMessage)]
        if not user_messages:
            return ConversationSummary(
                tenant_id=tenant_id,
                customer_phone=customer_phone,
                thread_id=thread_id,
                summary="No user messages to summarize",
            )

        formatted = self.format_messages_for_summary(messages)

        try:
            prompt = SUMMARIZATION_PROMPT.format(messages=formatted)
            result = await self.llm.ainvoke([SystemMessage(content=prompt)])

            import json
            try:
                parsed = json.loads(result.content)
            except json.JSONDecodeError:
                parsed = {
                    "summary": result.content[:500],
                    "key_entities": {},
                    "topics": [],
                    "sentiment": "neutral",
                    "decisions": [],
                }

            return ConversationSummary(
                tenant_id=tenant_id,
                customer_phone=customer_phone,
                thread_id=thread_id,
                summary=parsed.get("summary", "")[:1000],
                key_entities=parsed.get("key_entities", {}),
                topics=parsed.get("topics", []),
                sentiment=parsed.get("sentiment", "neutral"),
                decisions=parsed.get("decisions", []),
                message_count=len(user_messages),
                token_estimate=self.estimate_tokens(messages),
            )
        except Exception as e:
            logger.exception(f"Failed to generate summary: {e}")
            return ConversationSummary(
                tenant_id=tenant_id,
                customer_phone=customer_phone,
                thread_id=thread_id,
                summary="Summary generation failed",
            )

    async def save_summary(self, summary: ConversationSummary) -> None:
        db = self._get_db()
        doc = summary.model_dump()
        doc["created_at"] = doc["created_at"] if isinstance(doc["created_at"], datetime) else datetime.now(timezone.utc)
        doc["updated_at"] = datetime.now(timezone.utc)

        await db["conversation_summaries"].update_one(
            {"thread_id": summary.thread_id, "tenant_id": summary.tenant_id},
            {"$set": doc},
            upsert=True,
        )

    async def get_latest_summary(
        self, tenant_id: str, customer_phone: str
    ) -> Optional[ConversationSummary]:
        db = self._get_db()
        doc = await db["conversation_summaries"].find_one(
            {"tenant_id": tenant_id, "customer_phone": customer_phone},
            sort=[("created_at", -1)],
        )
        if doc:
            doc.pop("_id", None)
            return ConversationSummary(**doc)
        return None


summarizer = ConversationSummarizer()