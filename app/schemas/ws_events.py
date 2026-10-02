from datetime import datetime, timezone
from typing import Any, Dict, Literal
from pydantic import BaseModel, Field

WSEventType = Literal[
    "message.new",
    "message.status",
    "message.read",
    "unread.count",
    "order.created",
    "order.updated",
    "order.cancelled",
    "report.weekly_generated",
    "agent.step",
    "agent.reply",
]


class WSEvent(BaseModel):
    """Envelope for every realtime event pushed over a websocket connection."""

    type: WSEventType
    payload: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def to_json_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "payload": self.payload,
            "timestamp": self.timestamp.isoformat(),
        }
