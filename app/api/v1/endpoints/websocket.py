import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from core.events import manager

logger = logging.getLogger(__name__)

websocket_router = APIRouter()


@websocket_router.websocket("/ws/tenants/{tenant_id}/orders")
async def tenant_orders_websocket(websocket: WebSocket, tenant_id: str):
    """
    Real-time WebSocket channel for restaurant owner dashboard.
    Emits instant updates whenever a WhatsApp customer places, modifies, or cancels an order.
    """
    await manager.connect(tenant_id, websocket)
    try:
        while True:
            # Keep connection open and receive client heartbeats/pings
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(tenant_id, websocket)
    except Exception as e:
        logger.error(f"WebSocket error for tenant {tenant_id}: {e}")
        manager.disconnect(tenant_id, websocket)
