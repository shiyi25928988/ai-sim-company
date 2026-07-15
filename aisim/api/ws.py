"""WebSocket 管理 - 前端实时通信 (见 §六 前端 WS 协议)。

Hub 把渲染事件 (agent_message / agent_action / agent_created /
meeting_start / state_snapshot) 广播到所有连接的前端。
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

ws_router = APIRouter()


class WebSocketManager:
    """管理前端 WebSocket 连接并广播渲染事件。"""

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
        """广播一个渲染事件到所有前端 (见 §六 协议)。"""
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
            # 前端可发控制指令 (播放/暂停/加速); 暂只保持连接
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
