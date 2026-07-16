"""Agent personal memory management (see §四: Company Hub does not maintain Agent personal memory).

Maintained independently inside each Agent container; during the MVP phase local SQLite + vector retrieval can be used,
and Hermes' built-in memory system can be integrated later.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class MemoryEntry:
    """A single memory entry."""

    id: str
    content: str
    memory_type: str = "observation"  # observation | reflection | action | skill
    timestamp: float = 0.0
    importance: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class MemoryManager:
    """Agent memory manager - runs inside the container."""

    def __init__(self, agent_id: str) -> None:
        self.agent_id = agent_id
        self._entries: list[MemoryEntry] = []

    def add(self, entry: MemoryEntry) -> None:
        """Append a memory entry."""
        self._entries.append(entry)

    def recall(self, query: str, limit: int = 10) -> list[MemoryEntry]:
        """Retrieve relevant memories (TODO: integrate vector retrieval / FTS5)."""
        # TODO: perform semantic/keyword retrieval by query and sort by importance
        return self._entries[-limit:]

    def recent(self, limit: int = 20) -> list[MemoryEntry]:
        return self._entries[-limit:]

    def clear(self) -> None:
        self._entries.clear()
