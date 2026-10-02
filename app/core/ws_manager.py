"""
Generic websocket pub/sub, keyed by an arbitrary scope string.

Two scopes are used today:
  - "tenant:<tenant_id>"  — a restaurant owner's dashboard (inbox, orders)
  - "founder"             — the founder console (growth agent chat trace)

Replaces the deleted core/ws_inbox.py (ws_inbox_manager was tenant-only;
this one is scope-generic so the founder console can reuse it).
"""

import asyncio
import json
import logging
from collections import defaultdict
from typing import Dict, List, Set

from fastapi import WebSocket

from schemas.ws_events import WSEvent

logger = logging.getLogger(__name__)


class WSConnectionManager:
    def __init__(self) -> None:
        self._connections: Dict[str, Set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, scope_key: str, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections[scope_key].add(websocket)
        logger.info(
            f"[ws] connected scope={scope_key} total={len(self._connections[scope_key])}"
        )

    async def disconnect(self, scope_key: str, websocket: WebSocket) -> None:
        async with self._lock:
            conns = self._connections.get(scope_key)
            if conns and websocket in conns:
                conns.discard(websocket)
                if not conns:
                    self._connections.pop(scope_key, None)
        logger.info(f"[ws] disconnected scope={scope_key}")

    async def broadcast(self, scope_key: str, event: WSEvent) -> None:
        conns = list(self._connections.get(scope_key, ()))
        if not conns:
            return

        # default=str covers datetime/ObjectId/etc. that can slip into a
        # payload built from a raw Mongo document — plain send_json() would
        # raise on those instead of broadcasting.
        payload_text = json.dumps(event.to_json_dict(), default=str)
        dead: List[WebSocket] = []
        for ws in conns:
            try:
                await ws.send_text(payload_text)
            except Exception as e:
                logger.warning(f"[ws] send failed scope={scope_key}: {e}")
                dead.append(ws)

        if dead:
            async with self._lock:
                remaining = self._connections.get(scope_key)
                if remaining:
                    for ws in dead:
                        remaining.discard(ws)

    @staticmethod
    def tenant_scope(tenant_id: str) -> str:
        return f"tenant:{tenant_id}"

    @staticmethod
    def founder_scope() -> str:
        return "founder"

    async def broadcast_to_tenant(self, tenant_id: str, event: WSEvent) -> None:
        await self.broadcast(self.tenant_scope(tenant_id), event)

    async def broadcast_to_founder(self, event: WSEvent) -> None:
        await self.broadcast(self.founder_scope(), event)


ws_manager = WSConnectionManager()
