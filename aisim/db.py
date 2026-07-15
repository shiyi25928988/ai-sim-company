"""SQLite 持久化 - 见架构设计文档 §十三 (aisim/db.py)。

用 key-value 表保存 Hub 的易失状态 (tick / 经济 / LLM 用量)，使 Hub 进程重启后
能恢复进度。Agent/Task/Skill 等热状态走 Redis (Redis AOF 已持久化)，这里只补
Hub 内存态。同步 sqlite3 (调用频次低，每 tick 一次)。
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

DEFAULT_DB_PATH = "data/aisim.db"


class Database:
    """SQLite key-value 状态存储。"""

    def __init__(self, path: str | Path = DEFAULT_DB_PATH) -> None:
        self.path = Path(path)
        self._conn: sqlite3.Connection | None = None

    def connect(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value TEXT)"
        )
        self._conn.commit()

    def save_json(self, key: str, value: Any) -> None:
        """upsert 一个 JSON 值。"""
        if self._conn is None:
            return
        self._conn.execute(
            "INSERT OR REPLACE INTO state(key, value) VALUES(?, ?)",
            (key, json.dumps(value, default=str)),
        )
        self._conn.commit()

    def load_json(self, key: str) -> Any | None:
        if self._conn is None:
            return None
        row = self._conn.execute(
            "SELECT value FROM state WHERE key=?", (key,)
        ).fetchone()
        return json.loads(row[0]) if row else None

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None
