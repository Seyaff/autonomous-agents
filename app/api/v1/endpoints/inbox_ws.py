import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends

from core.database import get_database
from core.ws_manager import ws_manager
from middlewares.auth_middleware import get_current_user_ws

logger = logging.getLogger(__name__)

inbox_ws_router = APIRouter()


@inbox_ws_router.websocket("/ws/inbox")
async def inbox_websocket(websocket: WebSocket, database=Depends(get_database)):
    """
    Live push for the owner dashboard inbox: new messages, status updates,
    unread counts, and order events for the caller's active tenant.
    """
    user = await get_current_user_ws(websocket, database)
    if not user or user.get("role") != "OWNER" or not user.get("active_tenant_id"):
        await websocket.close(code=4401)
        return

    tenant_id = user["active_tenant_id"]
    scope_key = ws_manager.tenant_scope(tenant_id)

    await ws_manager.connect(scope_key, websocket)
    try:
        while True:
            # The dashboard doesn't need to send anything; this just keeps
            # the connection open and drains client pings/pongs.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await ws_manager.disconnect(scope_key, websocket)
