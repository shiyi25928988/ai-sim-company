"""In-memory message bus + state store (replaces Redis).

Four communication modes (DM / Channel / Meeting / Announcement) are no-ops in simulated mode
(agents call the Hub directly; the frontend sees messages via emit_frontend).
State storage (agents/profiles/tasks/skills) uses an in-memory dict persisted to SQLite.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable

from aisim.shared import channels
from aisim.shared.models import Message, MessageType, Priority

logger = logging.getLogger(__name__)

# Hash names persisted to SQLite (loaded on startup via attach_db)
_PERSISTED_HASHES = [
    channels.KEY_AGENTS,
    channels.KEY_PROFILES,
    channels.KEY_TASKS,
    channels.KEY_SKILLS,
    channels.KEY_META,
]


class MessageBus:
    """In-memory message bus + state store (replaces Redis)."""

    def __init__(self) -> None:
        self._store: dict[str, dict[str, Any]] = {}  # hash-like: {name: {key: value}}
        self._strings: dict[str, Any] = {}
        self._db: Any = None  # Database (SQLite), attached via attach_db
        self._listener_task: asyncio.Task | None = None

    async def connect(self, url: str = "") -> None:
        """No-op (Redis removed). Kept for API compatibility."""
        logger.info("MessageBus ready (in-memory + SQLite)")

    def attach_db(self, db: Any) -> None:
        """Attach a SQLite Database and load persisted hashes into memory."""
        self._db = db
        for name in _PERSISTED_HASHES:
            data = db.load_json(f"hash:{name}")
            if isinstance(data, dict):
                self._store[name] = data
                logger.info("Loaded %d entries from SQLite hash:%s", len(data), name)

    async def close(self) -> None:
        if self._listener_task is not None:
            self._listener_task.cancel()
            self._listener_task = None

    # ── Messaging (in-memory no-ops; simulated agents call Hub directly) ──

    async def publish(self, channel: str, data: dict) -> None:
        logger.debug("publish (in-memory no-op): %s", channel)

    async def broadcast_tick(self, tick: int) -> None:
        logger.debug("broadcast_tick (in-memory no-op): tick=%d", tick)

    async def send(self, message: Message) -> None:
        logger.debug("send (in-memory no-op): %s -> %s", message.sender, message.recipients)

    async def send_dm(self, sender: str, recipient: str, content: str) -> None:
        logger.debug("send_dm (in-memory no-op): %s -> %s", sender, recipient)

    async def broadcast_announcement(self, sender: str, content: str) -> None:
        logger.debug("broadcast_announcement (in-memory no-op): %s", sender)

    async def listen_agents(self, handler: Callable[[dict], Awaitable[None]]) -> None:
        """No-op (simulated agents call the Hub directly, not via Pub/Sub)."""
        logger.info("listen_agents (in-memory no-op; simulated agents call Hub directly)")

    # ── JSON state storage (hash) ──

    async def hset_json(self, name: str, key: str, value: Any) -> None:
        self._store.setdefault(name, {})[key] = value
        self._persist_hash(name)

    async def hget_json(self, name: str, key: str) -> Any:
        return self._store.get(name, {}).get(key)

    async def hgetall_json(self, name: str) -> dict[str, Any]:
        return dict(self._store.get(name, {}))

    async def hdel(self, name: str, *keys: str) -> None:
        h = self._store.get(name, {})
        for k in keys:
            h.pop(k, None)
        self._persist_hash(name)

    # ── JSON state storage (string) ──

    async def set_json(self, key: str, value: Any) -> None:
        self._strings[key] = value
        if self._db:
            self._db.save_json(key, value)

    async def get_json(self, key: str) -> Any:
        if key in self._strings:
            return self._strings[key]
        if self._db:
            return self._db.load_json(key)
        return None

    async def delete(self, *keys: str) -> None:
        for k in keys:
            self._strings.pop(k, None)
            self._store.pop(k, None)
            if self._db:
                self._db.delete(k)

    def _persist_hash(self, name: str) -> None:
        if self._db:
            self._db.save_json(f"hash:{name}", self._store.get(name, {}))
