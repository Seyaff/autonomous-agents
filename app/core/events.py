"""Thin domain helper over core.ws_manager for order realtime events."""

from typing import Any, Dict

from core.ws_manager import ws_manager
from schemas.ws_events import WSEvent


async def broadcast_order_update(
    tenant_id: str, event_type: str, order_data: Dict[str, Any]
) -> None:
    event = WSEvent(type=event_type, payload={"order": order_data})
    await ws_manager.broadcast_to_tenant(tenant_id, event)
