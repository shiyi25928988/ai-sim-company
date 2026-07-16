"""WebSocket management - real-time frontend communication (see §六 frontend WS protocol).

The Hub broadcasts render events (agent_message / agent_action / agent_created /
meeting_start / state_snapshot) to all connected frontends.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

ws_router = APIRouter()


class WebSocketManager:
    """Manages frontend WebSocket connections and broadcasts render events."""

    def __init__(self) -> None:
        self._connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.append(ws)
        logger.info("前端 WS 已连接 (共 %d)", len(self._connections))

    def disconnect(self, ws: WebSocket) -> None:
        if ws in self._connections:
            self._connections.remove(ws)

    async def broadcast(self, event: dict[str, Any]) -> None:
        """Broadcast a render event to all frontends (see §六 protocol)."""
        payload = json.dumps(event, default=str)
        dead = []
        for ws in self._connections:
            try:
                await ws.send_text(payload)
            except Exception:  # noqa: BLE001
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


ws_manager = WebSocketManager()


@ws_router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await ws_manager.connect(websocket)
    try:
        while True:
            # The frontend may send control commands (play/pause/speed up); for now only keeps the connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
