import json
import logging
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Depends, status
from core.ws_inbox import ws_inbox_manager, authenticate_ws_inbox
from core.ws_events import WSEvent
from core.database import get_database

logger = logging.getLogger(__name__)

ws_inbox_router = APIRouter()


@ws_inbox_router.websocket("/ws/inbox/{tenant_id}")
async def inbox_websocket(
    websocket: WebSocket,
    tenant_id: str,
    conversation_id: Optional[str] = Query(None),
):
    """
    Main inbox WebSocket connection.
    
    Query params:
    - conversation_id: Optional conversation to subscribe to immediately
    
    Auth: Cookie-based JWT (access_token)
    """
    # Authenticate
    user_id = await authenticate_ws_inbox(websocket, tenant_id)
    if not user_id:
        return

    # Connect
    await ws_inbox_manager.connect(tenant_id, websocket)

    # Subscribe to conversation if provided
    if conversation_id:
        await ws_inbox_manager.subscribe_conversation(tenant_id, conversation_id, websocket)

    try:
        while True:
            # Receive messages from client
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                await handle_client_message(tenant_id, user_id, message)
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON from tenant {tenant_id}: {data}")
            except Exception as e:
                logger.exception(f"Error handling client message: {e}")

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for tenant {tenant_id}, user {user_id}")
    except Exception as e:
        logger.exception(f"WebSocket error for tenant {tenant_id}: {e}")
    finally:
        ws_inbox_manager.disconnect(tenant_id, websocket)


async def handle_client_message(tenant_id: str, user_id: str, message: dict):
    """Handle incoming client messages."""
    msg_type = message.get("type")
    payload = message.get("payload", {})

    if msg_type == "subscribe":
        conversation_id = payload.get("conversation_id")
        if conversation_id:
            # The connection manager handles subscription via the websocket instance
            # This is a no-op here since subscription is handled at connection time
            pass

    elif msg_type == "unsubscribe":
        conversation_id = payload.get("conversation_id")
        if conversation_id:
            # Handled by connection manager on disconnect
            pass

    elif msg_type == "send":
        # Owner sending a message to customer
        conversation_id = payload.get("conversation_id")
        content = payload.get("content")
        msg_type = payload.get("type", "text")
        media = payload.get("media")

        if not conversation_id or not content:
            return

        # Import here to avoid circular imports
        from services.message_service import message_service
        await message_service.persist_outbound(
            conversation_id=payload["conversation_id"],
            tenant_id=tenant_id,
            content=content,
            message_type=payload.get("type", "text"),
            sender="human",
        )

    elif msg_type == "read":
        conversation_id = payload.get("conversation_id")
        message_id = payload.get("message_id")
        if conversation_id and message_id:
            from services.message_service import message_service
            await message_service.mark_message_read(message_id, tenant_id)

    elif msg_type == "ping":
        # Heartbeat - respond with pong
        pass


@ws_inbox_router.websocket("/ws/inbox/{tenant_id}/conv/{conversation_id}")
async def conversation_websocket(
    websocket: WebSocket,
    tenant_id: str,
    conversation_id: str,
):
    """
    Per-conversation WebSocket for focused real-time updates.
    """
    user_id = await authenticate_ws_inbox(websocket, tenant_id)
    if not user_id:
        return

    await ws_inbox_manager.connect(tenant_id, websocket)
    await ws_inbox_manager.subscribe_conversation(tenant_id, conversation_id, websocket)

    try:
        # Send initial conversation data
        db = get_database()
        conv = await db.conversations.find_one({"conversation_id": conversation_id, "tenant_id": tenant_id})
        if conv:
            conv.pop("_id", None)
            # Send conversation data and recent messages
            await websocket.send_text(json.dumps({
                "type": "init",
                "payload": {"conversation": conv}
            }))

        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                await handle_client_message(tenant_id, user_id, message)
            except json.JSONDecodeError:
                pass
            except Exception as e:
                logger.exception(f"Error handling message: {e}")

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.exception(f"Conversation WS error: {e}")
    finally:
        ws_inbox_manager.disconnect(tenant_id, websocket)