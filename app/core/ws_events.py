from datetime import datetime
from typing import Any, Dict, Literal, Optional
from pydantic import BaseModel, Field


class WSEvent(BaseModel):
    type: Literal[
        "message.new",
        "message.status",
        "message.read",
        "conversation.new",
        "conversation.update",
        "conversation.archive",
        "unread.count",
        "agent.status",
        "notification",
        "typing.start",
        "typing.stop",
    ]
    payload: Dict[str, Any]
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


# Event factory functions for type safety

def new_message_event(conversation_id: str, message: dict, conversation: dict) -> WSEvent:
    return WSEvent(
        type="message.new",
        payload={
            "conversation_id": conversation_id,
            "message": message,
            "conversation": conversation,
        },
    )


def message_status_event(message_id: str, conversation_id: str, status: str) -> WSEvent:
    return WSEvent(
        type="message.status",
        payload={
            "message_id": message_id,
            "conversation_id": conversation_id,
            "status": status,
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


def message_read_event(message_id: str, conversation_id: str, read_by: str = "owner") -> WSEvent:
    return WSEvent(
        type="message.read",
        payload={
            "message_id": message_id,
            "conversation_id": conversation_id,
            "read_by": read_by,
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


def conversation_new_event(conversation: dict) -> WSEvent:
    return WSEvent(
        type="conversation.new",
        payload=conversation,
    )


def conversation_update_event(conversation_id: str, updates: dict) -> WSEvent:
    return WSEvent(
        type="conversation.update",
        payload={"conversation_id": conversation_id, **updates},
    )


def conversation_archive_event(conversation_id: str) -> WSEvent:
    return WSEvent(
        type="conversation.archive",
        payload={"conversation_id": conversation_id},
    )


def unread_count_event(total_unread: int, conversations: list) -> WSEvent:
    return WSEvent(
        type="unread.count",
        payload={
            "total_unread": total_unread,
            "conversations": conversations,
        },
    )


def agent_status_event(conversation_id: str, status: str, preview: str = "") -> WSEvent:
    return WSEvent(
        type="agent.status",
        payload={
            "conversation_id": conversation_id,
            "status": status,
            "preview": preview,
        },
    )


def notification_event(notification_type: str, data: dict) -> WSEvent:
    return WSEvent(
        type="notification",
        payload={"type": notification_type, **data},
    )


def typing_start_event(conversation_id: str, participant: dict) -> WSEvent:
    return WSEvent(
        type="typing.start",
        payload={
            "conversation_id": conversation_id,
            "participant": participant,
        },
    )


def typing_stop_event(conversation_id: str, participant: dict) -> WSEvent:
    return WSEvent(
        type="typing.stop",
        payload={
            "conversation_id": conversation_id,
            "participant": participant,
        },
    )