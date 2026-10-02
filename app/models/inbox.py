from datetime import datetime
from typing import Optional, List, Literal
from pydantic import BaseModel, Field
from bson import ObjectId


class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid objectid")
        return ObjectId(v)

    @classmethod
    def __get_pydantic_json_schema__(cls, field_schema):
        field_schema.update(type="string")


class MediaInfo(BaseModel):
    url: str
    mime_type: str
    filename: Optional[str] = None
    size: Optional[int] = None
    caption: Optional[str] = None


class AgentMeta(BaseModel):
    agent_type: Literal["ai", "human"] = "ai"
    model: Optional[str] = None
    tokens_used: Optional[int] = None
    tools_called: List[str] = []


class MessagePreview(BaseModel):
    content: str
    sender: Literal["customer", "agent", "system"]
    timestamp: datetime
    type: Literal["text", "image", "document", "audio", "location", "template", "interactive"]


class Conversation(BaseModel):
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    conversation_id: str = Field(..., description="conv_{tenant_id}_{phone}")
    tenant_id: str
    customer_phone: str
    customer_name: str = ""
    customer_avatar: Optional[str] = None
    status: Literal["open", "closed", "archived"] = "open"
    last_message: Optional[MessagePreview] = None
    unread_count: int = 0
    tags: List[str] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_activity_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


class Message(BaseModel):
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    message_id: str = Field(..., description="msg_{uuid}")
    wamid: Optional[str] = None
    conversation_id: str
    tenant_id: str
    sender: Literal["customer", "agent", "system"]
    sender_phone: Optional[str] = None
    content: str
    type: Literal["text", "image", "document", "audio", "location", "template", "interactive"] = "text"
    media: Optional[MediaInfo] = None
    status: Literal["sending", "sent", "delivered", "read", "failed"] = "sending"
    agent_metadata: Optional[AgentMeta] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    delivered_at: Optional[datetime] = None
    read_at: Optional[datetime] = None

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


class ConversationParticipant(BaseModel):
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    conversation_id: str
    tenant_id: str
    participant_type: Literal["customer", "agent", "human"]
    participant_id: str
    participant_name: str
    is_typing: bool = False
    last_seen_at: Optional[datetime] = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


class PushSubscription(BaseModel):
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    user_id: str
    tenant_id: str
    endpoint: str
    p256dh: str
    auth: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}