import json
import logging
from typing import Dict, Set, Any
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages active WebSocket connections per tenant for real-time order and notification broadcasts."""

    def __init__(self):
        # Map tenant_id -> set of active WebSockets
        self.active_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, tenant_id: str, websocket: WebSocket):
        await websocket.accept()
        if tenant_id not in self.active_connections:
            self.active_connections[tenant_id] = set()
        self.active_connections[tenant_id].add(websocket)
        logger.info(f"WebSocket client connected to tenant [{tenant_id}]. Total active: {len(self.active_connections[tenant_id])}")

    def disconnect(self, tenant_id: str, websocket: WebSocket):
        if tenant_id in self.active_connections:
            self.active_connections[tenant_id].discard(websocket)
            if not self.active_connections[tenant_id]:
                del self.active_connections[tenant_id]
        logger.info(f"WebSocket client disconnected from tenant [{tenant_id}]")

    async def broadcast_to_tenant(self, tenant_id: str, message: Dict[str, Any]):
        """Broadcasts a JSON message payload to all active clients of the tenant."""
        if tenant_id not in self.active_connections:
            return

        payload = json.dumps(message, default=str)
        dead_connections = set()

        for connection in self.active_connections[tenant_id]:
            try:
                await connection.send_text(payload)
            except Exception as e:
                logger.warning(f"Failed to send WebSocket message: {e}")
                dead_connections.add(connection)

        for dead in dead_connections:
            self.disconnect(tenant_id, dead)


manager = ConnectionManager()


async def broadcast_order_update(tenant_id: str, event_type: str, order_data: Dict[str, Any]):
    """Helper to dispatch real-time order events to connected owner dashboards."""
    await manager.broadcast_to_tenant(
        tenant_id=tenant_id,
        message={
            "event": event_type,  # "order.created", "order.updated", "order.cancelled"
            "data": order_data
        }
    )
