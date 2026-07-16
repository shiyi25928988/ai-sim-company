"""SQLite persistence - see architecture design doc §十三 (aisim/db.py).

Uses a key-value table to persist the Hub's volatile state (tick / economy / LLM usage)
so the Hub process can resume progress after restart. Hot state such as Agent/Task/Skill
lives in Redis (Redis AOF already persists it); this only supplements the Hub's in-memory
state. Synchronous sqlite3 (low call frequency, once per tick).
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

DEFAULT_DB_PATH = "data/aisim.db"


class Database:
    """SQLite key-value state store."""

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
        """Upsert a JSON value."""
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

    def delete(self, key: str) -> None:
        """Delete a key."""
        if self._conn is None:
            return
        self._conn.execute("DELETE FROM state WHERE key=?", (key,))
        self._conn.commit()

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None
