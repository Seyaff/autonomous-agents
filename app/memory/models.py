from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class ConversationSummary(BaseModel):
    tenant_id: str
    customer_phone: str
    thread_id: str
    summary: str
    key_entities: Dict[str, Any] = Field(default_factory=dict)
    topics: List[str] = Field(default_factory=list)
    sentiment: str = "neutral"
    decisions: List[str] = Field(default_factory=list)
    message_count: int = 0
    token_estimate: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class AgentContext(BaseModel):
    system_prompt: str
    recent_messages: List[Dict[str, Any]] = Field(default_factory=list)
    customer_profile: Optional[Dict[str, Any]] = None
    conversation_summary: Optional[ConversationSummary] = None


class SummarizationTrigger(BaseModel):
    should_summarize: bool
    reason: str
    turn_count: int
    token_estimate: int