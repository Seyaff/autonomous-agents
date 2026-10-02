import json
import logging
from typing import Dict, Set, Optional
from fastapi import WebSocket, WebSocketDisconnect, status
from utils.jwt import verify_jwt_token
from core.database import get_database
from core.ws_events import WSEvent

logger = logging.getLogger(__name__)


class InboxConnectionManager:
    """Manages WebSocket connections for inbox real-time updates."""

    def __init__(self):
        # tenant_id -> set of WebSocket connections
        self.tenant_connections: Dict[str, Set[WebSocket]] = {}
        # conversation_id -> tenant_id -> set of WebSocket connections
        self.conv_connections: Dict[str, Dict[str, Set[WebSocket]]] = {}

    async def connect(self, tenant_id: str, websocket: WebSocket):
        """Accept connection and register for tenant."""
        await websocket.accept()
        if tenant_id not in self.tenant_connections:
            self.tenant_connections[tenant_id] = set()
        self.tenant_connections[tenant_id].add(websocket)
        logger.info(f"WebSocket connected for tenant [{tenant_id}]. Total: {len(self.tenant_connections[tenant_id])}")

    def disconnect(self, tenant_id: str, websocket: WebSocket):
        """Remove connection from tenant and conversation tracking."""
        if tenant_id in self.tenant_connections:
            self.tenant_connections[tenant_id].discard(websocket)
            if not self.tenant_connections[tenant_id]:
                del self.tenant_connections[tenant_id]

        # Clean up conversation connections
        for conv_id, tenants in self.conv_connections.items():
            if tenant_id in tenants:
                tenants[tenant_id].discard(websocket)
                if not tenants[tenant_id]:
                    del tenants[tenant_id]
            if not tenants:
                del self.conv_connections[conv_id]

        logger.info(f"WebSocket disconnected for tenant [{tenant_id}]")

    async def subscribe_conversation(self, tenant_id: str, conversation_id: str, websocket: WebSocket):
        """Subscribe a connection to a specific conversation."""
        if conversation_id not in self.conv_connections:
            self.conv_connections[conversation_id] = {}
        if tenant_id not in self.conv_connections[conversation_id]:
            self.conv_connections[conversation_id][tenant_id] = set()
        self.conv_connections[conversation_id][tenant_id].add(websocket)

    def unsubscribe_conversation(self, conversation_id: str, tenant_id: str, websocket: WebSocket):
        """Unsubscribe from a conversation."""
        if conversation_id in self.conv_connections and tenant_id in self.conv_connections[conversation_id]:
            self.conv_connections[conversation_id][tenant_id].discard(websocket)
            if not self.conv_connections[conversation_id][tenant_id]:
                del self.conv_connections[conversation_id][tenant_id]
            if not self.conv_connections[conversation_id]:
                del self.conv_connections[conversation_id]

    async def send_to_websocket(self, websocket: WebSocket, event: "WSEvent"):
        """Send event to a single WebSocket."""
        try:
            await websocket.send_text(event.model_dump_json())
        except Exception as e:
            logger.warning(f"Failed to send to WebSocket: {e}")

    async def broadcast_to_tenant(self, tenant_id: str, event: "WSEvent"):
        """Broadcast event to all connections for a tenant."""
        if tenant_id not in self.tenant_connections:
            return

        payload = event.model_dump_json()
        dead_connections = set()

        for websocket in self.tenant_connections[tenant_id]:
            try:
                await websocket.send_text(payload)
            except Exception as e:
                logger.warning(f"Failed to send to tenant {tenant_id}: {e}")
                dead_connections.add(websocket)

        # Clean up dead connections
        for dead in dead_connections:
            self.disconnect(tenant_id, dead)

    async def send_to_conversation(self, tenant_id: str, conversation_id: str, event: "WSEvent"):
        """Send event to all connections subscribed to a conversation."""
        if conversation_id not in self.conv_connections:
            return
        if tenant_id not in self.conv_connections.get(conversation_id, {}):
            return

        payload = event.model_dump_json()
        dead_connections = set()

        for websocket in self.conv_connections[conversation_id].get(tenant_id, set()):
            try:
                await websocket.send_text(payload)
            except Exception as e:
                logger.warning(f"Failed to send to conversation {conversation_id}: {e}")
                dead_connections.add(websocket)

        for dead in dead_connections:
            if conversation_id in self.conv_connections and tenant_id in self.conv_connections.get(conversation_id, {}):
                self.conv_connections[conversation_id][tenant_id].discard(dead)


# Global instance
ws_inbox_manager = InboxConnectionManager()


async def authenticate_ws_inbox(websocket: WebSocket, tenant_id: str) -> Optional[str]:
    """Authenticate WebSocket connection using cookie-based JWT."""
    try:
        # Get access token from cookie
        token = websocket.cookies.get("access_token")
        if not token:
            logger.warning(f"WS auth failed: no access_token cookie for tenant {tenant_id}")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Missing authentication")
            return None

        # Verify JWT token
        try:
            user_id = verify_jwt_token(token)
        except Exception as e:
            logger.warning(f"WS auth failed: invalid token for tenant {tenant_id}: {e}")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token")
            return None

        # Verify user has access to this tenant
        db = get_database()
        user = await db.users.find_one({"user_id": user_id})
        if not user:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="User not found")
            return None

        # Check if user owns or has access to this tenant
        user_tenants = user.get("tenants", [])
        active_tenant = user.get("active_tenant_id")

        if tenant_id not in user_tenants and tenant_id != active_tenant:
            logger.warning(f"WS auth failed: user {user_id} not authorized for tenant {tenant_id}")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Not authorized for this tenant")
            return None

        logger.info(f"WS authenticated: user={user_id}, tenant={tenant_id}")
        return user_id

    except Exception as e:
        logger.exception(f"WS auth error: {e}")
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR, reason="Authentication error")
        return None