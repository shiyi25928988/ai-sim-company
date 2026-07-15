"""事件系统 - 市场事件 / 随机事件 (见 §三 event_bus)。"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable

logger = logging.getLogger(__name__)


@dataclass
class SimEvent:
    """仿真事件。"""

    id: str
    kind: str  # market | random | milestone | crisis
    description: str
    impact: dict = field(default_factory=dict)  # e.g. {"capital": -50000}


class EventBus:
    """市场事件与随机事件的总线。"""

    def __init__(self) -> None:
        self._subscribers: list[Callable[[SimEvent], None]] = []
        self._queue: list[SimEvent] = []

    def subscribe(self, handler: Callable[[SimEvent], None]) -> None:
        self._subscribers.append(handler)

    def emit(self, event: SimEvent) -> None:
        for handler in self._subscribers:
            handler(event)

    def schedule(self, event: SimEvent) -> None:
        """排队一个将在后续 Tick 触发的事件。"""
        self._queue.append(event)

    def drain(self) -> list[SimEvent]:
        """取出并触发本 Tick 所有事件。"""
        events, self._queue = self._queue, []
        for e in events:
            self.emit(e)
        return events
