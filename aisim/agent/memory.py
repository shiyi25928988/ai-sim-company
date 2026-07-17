"""Agent personal memory management (see §四: Company Hub does not maintain Agent personal memory).

Maintained independently inside each Agent container; during the MVP phase local SQLite + vector retrieval can be used,
and Hermes' built-in memory system can be integrated later.
"""

from __future__ import annotations

import re
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
        """Retrieve relevant memories by keyword overlap + importance + recency.

        Scores each memory: keyword overlap with the query (0.6) + importance (0.2) +
        recency (0.2); returns the top `limit`. Falls back to recent() when the query
        is empty or there are no entries.
        """
        if not query or not self._entries:
            return self._entries[-limit:]
        q_tokens = set(re.findall(r"[a-z0-9]+", query.lower()))
        n = len(self._entries)
        scored: list[tuple[float, MemoryEntry]] = []
        for i, e in enumerate(self._entries):
            recency = (i + 1) / n
            e_tokens = set(re.findall(r"[a-z0-9]+", (e.content or "").lower()))
            overlap = len(q_tokens & e_tokens) / max(len(q_tokens), 1)
            importance = max(0.0, min(1.0, e.importance))
            score = overlap * 0.6 + importance * 0.2 + recency * 0.2
            scored.append((score, e))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [e for _, e in scored[:limit]]

    def recent(self, limit: int = 20) -> list[MemoryEntry]:
        return self._entries[-limit:]

    def clear(self) -> None:
        self._entries.clear()
