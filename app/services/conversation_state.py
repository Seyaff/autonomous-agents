"""
Conversation ownership and queue grouping — the single source of truth.

The queue group is computed here on the server and returned as a field, so
the frontend never guesses it. The same rules are expressed as Mongo filters
in GROUP_FILTERS for the list endpoint, and must stay in sync with
compute_group() (precedence: escalation > resolved > owner > agent).
"""

from typing import Any, Dict, Optional

CLOSED_STATUSES = ("closed", "archived")

GROUP_ORDER = ("needs_you", "owner_handling", "agent_handling", "resolved")

GROUP_FILTERS: Dict[str, Dict[str, Any]] = {
    "needs_you": {"escalation.active": True},
    "resolved": {
        "escalation.active": {"$ne": True},
        "status": {"$in": list(CLOSED_STATUSES)},
    },
    "owner_handling": {
        "escalation.active": {"$ne": True},
        "status": {"$nin": list(CLOSED_STATUSES)},
        "handled_by": "owner",
    },
    "agent_handling": {
        "escalation.active": {"$ne": True},
        "status": {"$nin": list(CLOSED_STATUSES)},
        "handled_by": {"$ne": "owner"},
    },
}


def is_escalated(doc: Dict[str, Any]) -> bool:
    return bool((doc.get("escalation") or {}).get("active"))


def compute_group(doc: Dict[str, Any]) -> str:
    if is_escalated(doc):
        return "needs_you"
    if doc.get("status") in CLOSED_STATUSES:
        return "resolved"
    if doc.get("handled_by") == "owner":
        return "owner_handling"
    return "agent_handling"


def conversation_blocks_agent(conversation: Optional[Dict[str, Any]], tenant: Dict[str, Any]) -> bool:
    """True when the agent must not reply to this customer right now."""
    if tenant.get("agent_enabled", True) is False:
        return True
    if conversation is None:
        return False
    return conversation.get("handled_by") == "owner" or is_escalated(conversation)


def serialize_conversation(doc: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Public shape of a conversation: raw Mongo doc minus _id, plus the
    derived group and defaults for the ownership fields."""
    if doc is None:
        return None
    out = {k: v for k, v in doc.items() if k != "_id"}
    out["handled_by"] = doc.get("handled_by", "agent")
    out["handed_over_at"] = doc.get("handed_over_at")
    out["handed_over_by_user_id"] = doc.get("handed_over_by_user_id")
    out["escalation"] = doc.get("escalation")
    out["group"] = compute_group(doc)
    return out


async def broadcast_conversation_updated(tenant_id: str, doc: Optional[Dict[str, Any]]) -> None:
    """Push the new state of a conversation to the owner's dashboard, so the
    queue regroups and the takeover bar updates without a refresh."""
    if doc is None:
        return
    from core.ws_manager import ws_manager
    from schemas.ws_events import WSEvent

    await ws_manager.broadcast_to_tenant(
        tenant_id,
        WSEvent(type="conversation.updated", payload={"conversation": doc}),
    )
