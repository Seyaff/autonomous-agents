import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends

from core.database import get_database
from core.ws_manager import ws_manager
from middlewares.auth_middleware import get_current_user_ws, require_owner

logger = logging.getLogger(__name__)

inbox_ws_router = APIRouter()

# The browser can't send its login cookie to the websocket host (the page is on
# Vercel, the API on Render), so the page first asks for a short-lived one-use
# ticket over normal HTTP and passes it in the websocket URL.
TICKET_TTL = timedelta(seconds=60)


@inbox_ws_router.post("/ws/ticket")
async def issue_ws_ticket(current_user: dict = Depends(require_owner), database=Depends(get_database)):
    now = datetime.now(timezone.utc)
    ticket = secrets.token_urlsafe(32)
    await database["ws_tickets"].delete_many({"expires_at": {"$lt": now}})
    await database["ws_tickets"].insert_one({
        "ticket": ticket,
        "role": current_user.get("role"),
        "tenant_id": current_user["active_tenant_id"],
        "expires_at": now + TICKET_TTL,
    })
    return {"ticket": ticket, "expires_in": int(TICKET_TTL.total_seconds())}


async def _user_from_ticket(ticket: Optional[str], database) -> Optional[dict]:
    """Consumes the ticket. A ticket works once and only until it expires."""
    if not ticket:
        return None
    doc = await database["ws_tickets"].find_one_and_delete(
        {"ticket": ticket, "expires_at": {"$gt": datetime.now(timezone.utc)}}
    )
    if not doc:
        return None
    return {"role": doc.get("role"), "active_tenant_id": doc.get("tenant_id")}


@inbox_ws_router.websocket("/ws/inbox")
async def inbox_websocket(websocket: WebSocket, database=Depends(get_database)):
    """
    Live push for the owner dashboard inbox: new messages, status updates,
    unread counts, and order events for the caller's active tenant.
    """
    user = await _user_from_ticket(websocket.query_params.get("ticket"), database)
    if user is None:
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
