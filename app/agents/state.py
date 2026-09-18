import operator
from typing import Annotated, Sequence, TypedDict, List, Dict, Any, Optional
from langchain_core.messages import BaseMessage

class BaseAgentState(TypedDict):
    """Base state for WhatsApp conversational agents."""
    messages: Annotated[Sequence[BaseMessage], operator.add]
    tenant_id: str
    sender_phone: str
    session_id: str
