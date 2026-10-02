from datetime import datetime
from typing import Optional, List, Literal
from pydantic import BaseModel, Field


class MediaInfoSchema(BaseModel):
    url: str
    mime_type: str
    filename: Optional[str] = None
    size: Optional[int] = None
    caption: Optional[str] = None


class AgentMetaSchema(BaseModel):
    agent_type: Literal["ai", "human"] = "ai"
    model: Optional[str] = None
    tokens_used: Optional[int] = None
    tools_called: List[str] = []


class MessagePreviewSchema(BaseModel):
    content: str
    sender: Literal["customer", "agent", "system"]
    timestamp: datetime
    type: Literal["text", "image", "document", "audio", "location", "template", "interactive"]


class ConversationListItem(BaseModel):
    conversation_id: str
    tenant_id: str
    customer_phone: str
    customer_name: str
    customer_avatar: Optional[str] = None
    status: Literal["open", "closed", "archived"]
    last_message: Optional[MessagePreviewSchema] = None
    unread_count: int
    tags: List[str] = []
    created_at: datetime
    updated_at: datetime
    last_activity_at: datetime


class ConversationDetail(BaseModel):
    conversation_id: str
    tenant_id: str
    customer_phone: str
    customer_name: str
    customer_avatar: Optional[str] = None
    status: Literal["open", "closed", "archived"]
    last_message: Optional[MessagePreviewSchema] = None
    unread_count: int
    tags: List[str] = []
    created_at: datetime
    updated_at: datetime
    last_activity_at: datetime
    messages: List["MessageSchema"] = []
    participants: List["ParticipantSchema"] = []


class MediaInfoResponse(BaseModel):
    url: str
    mime_type: str
    filename: Optional[str] = None
    size: Optional[int] = None
    caption: Optional[str] = None


class MessageSchema(BaseModel):
    message_id: str
    wamid: Optional[str] = None
    conversation_id: str
    tenant_id: str
    sender: Literal["customer", "agent", "system"]
    sender_phone: Optional[str] = None
    content: str
    type: Literal["text", "image", "document", "audio", "location", "template", "interactive"]
    media: Optional[MediaInfoResponse] = None
    status: Literal["sending", "sent", "delivered", "read", "failed"]
    agent_metadata: Optional[AgentMetaSchema] = None
    created_at: datetime
    delivered_at: Optional[datetime] = None
    read_at: Optional[datetime] = None


class ParticipantSchema(BaseModel):
    participant_type: Literal["customer", "agent", "human"]
    participant_id: str
    participant_name: str
    is_typing: bool
    last_seen_at: Optional[datetime] = None


class ConversationListResponse(BaseModel):
    conversations: List[ConversationListItem]
    total: int
    page: int
    limit: int
    unread_total: int


class MessagesResponse(BaseModel):
    messages: List[MessageSchema]
    has_more: bool


# Request schemas
class SendMessageRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=4096)
    type: Literal["text", "image", "document", "audio", "location"] = "text"
    media: Optional[MediaInfoSchema] = None


class UpdateConversationRequest(BaseModel):
    status: Optional[Literal["open", "closed", "archived"]] = None
    tags: Optional[List[str]] = None


class MarkReadRequest(BaseModel):
    message_id: str


class AssignConversationRequest(BaseModel):
    human_id: str


class ConversationQueryParams(BaseModel):
    status: Optional[Literal["open", "closed", "archived"]] = None
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=20, ge=1, le=100)
    search: Optional[str] = None
    sort: Literal["last_activity_at", "created_at", "unread_count"] = "last_activity_at"


class MessageQueryParams(BaseModel):
    before_id: Optional[str] = None
    limit: int = Field(default=50, ge=1, le=100)


class PushSubscriptionRequest(BaseModel):
    endpoint: str
    p256dh: str
    auth: str


class PushNotificationPayload(BaseModel):
    title: str
    body: str
    icon: Optional[str] = None
    badge: Optional[str] = None
    data: dict = {}