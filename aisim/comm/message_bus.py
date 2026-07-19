"""Redis message bus - the sole backbone for all communication (see §六).

Four communication modes: DM / Channel / Meeting / Announcement.
All go through Redis Pub/Sub; channel naming is in aisim.shared.channels.
Also provides JSON state storage helpers (for ProfileRegistry / AgentManager persistence).
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Awaitable, Callable

from redis.asyncio import Redis
from redis.asyncio.retry import Retry
from redis.backoff import ExponentialBackoff
from redis.exceptions import (
    BusyLoadingError,
    ConnectionError as RedisConnectionError,
    TimeoutError as RedisTimeoutError,
)

from aisim.shared import channels
from aisim.shared.models import Message, MessageType, Priority

logger = logging.getLogger(__name__)

# Agent -> Hub event channels
_AGENT_EVENT_CHANNELS = [
    channels.AGENT_REGISTER,
    channels.AGENT_READY,
    channels.AGENT_OFFLINE,
    channels.HUB_ACTION,
    channels.HUB_SKILL_NEW,
]


class MessageBus:
    """Redis Pub/Sub message routing + state storage helpers."""

    def __init__(self) -> None:
        self._redis: Redis | None = None
        self._listener_task: asyncio.Task | None = None
        self._url: str = ""

    async def connect(self, redis_url: str) -> None:
        self._url = redis_url
        # Tolerate latency spikes on the Redis link (e.g. remote/LAN host with jitter):
        # generous read timeout + retry-on-error with exponential backoff + periodic
        # health checks so a stale connection is detected and rebuilt.
        self._redis = Redis.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=10,
            retry_on_error=[BusyLoadingError, RedisConnectionError, RedisTimeoutError],
            retry=Retry(ExponentialBackoff(cap=1.0, base=0.1), 3),
            health_check_interval=30,
        )
        await self._redis.ping()
        logger.info("MessageBus 已连接 Redis")

    async def close(self) -> None:
        if self._listener_task is not None:
            self._listener_task.cancel()
            self._listener_task = None
        if self._redis is not None:
            await self._redis.aclose()

    @property
    def redis(self) -> Redis:
        assert self._redis is not None, "MessageBus 未连接; 先调用 connect()"
        return self._redis

    # ── Base publish ──
    async def publish(self, channel: str, data: dict) -> None:
        await self.redis.publish(channel, json.dumps(data, default=str))

    async def broadcast_tick(self, tick: int) -> None:
        """Hub -> All Agents: simulation clock signal."""
        await self.publish(channels.SIMULATION_TICK, {"tick": tick})

    async def send(self, message: Message) -> None:
        """Deliver to inbox / channel / all by Message.type."""
        payload = json.dumps(message.__dict__, default=str)
        if message.type == MessageType.DM:
            for recipient in message.recipients:
                await self.redis.publish(channels.agent_inbox(recipient), payload)
        elif message.type == MessageType.ANNOUNCEMENT:
            await self.publish("agent:broadcast", message.__dict__)
        elif message.type == MessageType.CHANNEL and message.channel:
            await self.redis.publish(f"channel:{message.channel}", payload)
        else:
            await self.publish(channels.HUB_ACTION, message.__dict__)

    # ── Convenience constructors ──
    async def send_dm(self, sender: str, recipient: str, content: str) -> None:
        await self.send(
            Message(
                id=f"m-{sender}-{recipient}",
                type=MessageType.DM,
                sender=sender,
                recipients=[recipient],
                content=content,
                priority=Priority.NORMAL,
            )
        )

    async def broadcast_announcement(self, sender: str, content: str) -> None:
        await self.send(
            Message(
                id=f"a-{sender}",
                type=MessageType.ANNOUNCEMENT,
                sender=sender,
                recipients=[],
                content=content,
                priority=Priority.HIGH,
            )
        )

    # ── Listen for Agent reports ──
    async def listen_agents(self, handler: Callable[[dict], Awaitable[None]]) -> None:
        """Subscribe to Agent -> Hub channels, handing each message to the handler."""
        self._listener_task = asyncio.create_task(self._listen_loop(handler))

    async def _listen_loop(self, handler: Callable[[dict], Awaitable[None]]) -> None:
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(*_AGENT_EVENT_CHANNELS)
        try:
            async for msg in pubsub.listen():
                if msg["type"] != "message":
                    continue
                try:
                    data: Any = json.loads(msg["data"])
                    if isinstance(data, dict):
                        data["_channel"] = msg["channel"]
                        await handler(data)
                except Exception:  # noqa: BLE001
                    logger.exception("处理 Agent 事件失败: %s", msg)
        finally:
            await pubsub.unsubscribe(*_AGENT_EVENT_CHANNELS)
            await pubsub.aclose()

    # ── JSON state storage helpers (hash / string) ──
    async def set_json(self, key: str, value: Any) -> None:
        await self.redis.set(key, json.dumps(value, default=str))

    async def get_json(self, key: str) -> Any:
        v = await self.redis.get(key)
        return json.loads(v) if v else None

    async def hset_json(self, name: str, key: str, value: Any) -> None:
        await self.redis.hset(name, key, json.dumps(value, default=str))

    async def hget_json(self, name: str, key: str) -> Any:
        v = await self.redis.hget(name, key)
        return json.loads(v) if v else None

    async def hgetall_json(self, name: str) -> dict[str, Any]:
        items = await self.redis.hgetall(name)
        return {k: json.loads(v) for k, v in items.items()}

    async def hdel(self, name: str, *keys: str) -> None:
        if keys:
            await self.redis.hdel(name, *keys)

    async def delete(self, *keys: str) -> None:
        if keys:
            await self.redis.delete(*keys)
