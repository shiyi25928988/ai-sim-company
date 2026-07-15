"""仿真时钟 - 统一的 Tick 信号广播 (见 §三/§六 simulation:tick)。"""

from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable

logger = logging.getLogger(__name__)


class SimulationClock:
    """按固定间隔触发 Tick，并调用回调广播 simulation:tick。"""

    def __init__(self, interval_ms: int = 5000) -> None:
        self.interval_ms = interval_ms
        self.tick: int = 0
        self.speed: float = 1.0  # 1x / 10x / 60x
        self.on_tick: Callable[[int], Awaitable[None]] | None = None
        self._task: asyncio.Task | None = None
        self._running = False

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("仿真时钟启动: interval=%dms", self.interval_ms)

    async def stop(self) -> None:
        self._running = False
        if self._task is not None:
            self._task.cancel()
            self._task = None

    def set_speed(self, speed: float) -> None:
        """1x / 10x / 60x 倍速。"""
        self.speed = max(0.0, speed)

    @property
    def running(self) -> bool:
        return self._running

    async def _loop(self) -> None:
        while self._running:
            self.tick += 1
            if self.on_tick is not None:
                try:
                    await self.on_tick(self.tick)
                except Exception:  # noqa: BLE001
                    logger.exception("on_tick 回调异常")
            await asyncio.sleep(self.interval_ms / 1000.0 / max(self.speed, 1e-6))
