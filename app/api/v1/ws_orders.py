import json
import logging
from typing import Dict, List
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["Kitchen WebSocket"])

class OrderConnectionManager:
    def __init__(self):
        # Map tenant_id -> List[WebSocket]
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, tenant_id: str, websocket: WebSocket):
        await websocket.accept()
        if tenant_id not in self.active_connections:
            self.active_connections[tenant_id] = []
        self.active_connections[tenant_id].append(websocket)
        logger.info(f"WebSocket client connected for tenant {tenant_id}. Total active: {len(self.active_connections[tenant_id])}")

    def disconnect(self, tenant_id: str, websocket: WebSocket):
        if tenant_id in self.active_connections:
            if websocket in self.active_connections[tenant_id]:
                self.active_connections[tenant_id].remove(websocket)
            if not self.active_connections[tenant_id]:
                del self.active_connections[tenant_id]
        logger.info(f"WebSocket client disconnected for tenant {tenant_id}")

    async def broadcast_order_event(self, tenant_id: str, event_type: str, data: dict):
        """
        Broadcasts an event to all connected kitchen displays for a specific tenant.
        """
        if tenant_id not in self.active_connections:
            return

        payload = json.dumps({
            "event": event_type,
            "tenant_id": tenant_id,
            "data": data
        })

        dead_connections = []
        for connection in self.active_connections[tenant_id]:
            try:
                await connection.send_text(payload)
            except Exception as e:
                logger.warning(f"Error broadcasting to WebSocket: {e}")
                dead_connections.append(connection)

        for dead in dead_connections:
            self.disconnect(tenant_id, dead)

ws_manager = OrderConnectionManager()

@router.websocket("/orders/{tenant_id}")
async def kitchen_orders_stream(websocket: WebSocket, tenant_id: str):
    await ws_manager.connect(tenant_id, websocket)
    try:
        while True:
            # Keep connection alive, listen for ping or client ack
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("action") == "ping":
                    await websocket.send_text(json.dumps({"action": "pong"}))
            except Exception:
                pass
    except WebSocketDisconnect:
        ws_manager.disconnect(tenant_id, websocket)
    except Exception as e:
        logger.error(f"WebSocket exception: {e}")
        ws_manager.disconnect(tenant_id, websocket)
