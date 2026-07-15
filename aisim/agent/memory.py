"""Agent 个人记忆管理 (见 §四: Company Hub 不维护 Agent 个人记忆)。

每个 Agent 容器内独立维护; MVP 阶段可用本地 SQLite + 向量检索，
后续可接入 Hermes 内置记忆系统。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class MemoryEntry:
    """一条记忆。"""

    id: str
    content: str
    memory_type: str = "observation"  # observation | reflection | action | skill
    timestamp: float = 0.0
    importance: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class MemoryManager:
    """Agent 记忆管理器 - 容器内运行。"""

    def __init__(self, agent_id: str) -> None:
        self.agent_id = agent_id
        self._entries: list[MemoryEntry] = []

    def add(self, entry: MemoryEntry) -> None:
        """追加一条记忆。"""
        self._entries.append(entry)

    def recall(self, query: str, limit: int = 10) -> list[MemoryEntry]:
        """检索相关记忆 (TODO: 接入向量检索 / FTS5)。"""
        # TODO: 按 query 做语义/关键词检索并按 importance 排序
        return self._entries[-limit:]

    def recent(self, limit: int = 20) -> list[MemoryEntry]:
        return self._entries[-limit:]

    def clear(self) -> None:
        self._entries.clear()
