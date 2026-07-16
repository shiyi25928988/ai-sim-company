"""Event system - market events / random events (see §三 event_bus)."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable

logger = logging.getLogger(__name__)


@dataclass
class SimEvent:
    """A simulation event."""

    id: str
    kind: str  # market | random | milestone | crisis
    description: str
    impact: dict = field(default_factory=dict)  # e.g. {"capital": -50000}


class EventBus:
    """Bus for market events and random events."""

    def __init__(self) -> None:
        self._subscribers: list[Callable[[SimEvent], None]] = []
        self._queue: list[SimEvent] = []

    def subscribe(self, handler: Callable[[SimEvent], None]) -> None:
        self._subscribers.append(handler)

    def emit(self, event: SimEvent) -> None:
        for handler in self._subscribers:
            handler(event)

    def schedule(self, event: SimEvent) -> None:
        """Queue an event to be triggered in a later Tick."""
        self._queue.append(event)

    def drain(self) -> list[SimEvent]:
        """Pop and trigger all events for this Tick."""
        events, self._queue = self._queue, []
        for e in events:
            self.emit(e)
        return events
