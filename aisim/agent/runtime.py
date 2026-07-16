"""Agent runtime main program - runs inside each Agent container (see §五).

Boot sequence: connect Redis -> report in -> wait for Profile -> initialize Hermes ->
ready -> Tick main loop. Identity is 100% pushed by Company Hub via Redis;
the container itself only knows REDIS_URL and AGENT_ID.

Note: uses redis.asyncio (the successor to aioredis mentioned in the doc).
"""

from __future__ import annotations

import asyncio
import json
import logging

from redis.asyncio import Redis

from aisim.agent.memory import MemoryManager
from aisim.shared import channels

logger = logging.getLogger(__name__)

# Hermes Agent (Nous Research) - tool loop / memory / skill / LLM abstraction.
# This package is only available inside the Agent container; the Hub side should not import this module.
from hermes import HermesRuntime  # type: ignore[import-not-found]  # noqa: E402


async def wait_for_message(pubsub) -> dict:
    """Block waiting for the next Pub/Sub message and parse it into a dict."""
    async for msg in pubsub.listen():
        if msg["type"] == "message":
            return json.loads(msg["data"])
    raise RuntimeError("pubsub closed before a message arrived")


async def handle_tick(runtime: HermesRuntime, redis: Redis, agent_id: str) -> None:
    """Each Tick: check inbox -> Hermes.decide() (via Hub LLM Gateway) -> execute -> report."""
    # TODO: report decisions and execution results via hub:action; sync Skills to the company pool; heartbeat.
    logger.debug("[%s] tick", agent_id)


async def handle_message(runtime: HermesRuntime, message: dict) -> None:
    """Handle an inbox message (agent:{id}:inbox)."""
    logger.debug("[%s] message: %s", runtime, message)


async def main() -> None:
    import os

    agent_id = os.environ["AGENT_ID"]
    redis_url = os.environ["REDIS_URL"]
    redis = Redis.from_url(redis_url, decode_responses=True)
    pubsub = redis.pubsub()

    # ── Report in ──
    await redis.publish(
        channels.AGENT_REGISTER,
        json.dumps({"agent_id": agent_id, "status": "booting"}),
    )

    # ── Wait for Profile ──
    await pubsub.subscribe(channels.agent_profile(agent_id))
    profile_data = await wait_for_message(pubsub)
    logger.info("[%s] 收到 Profile", agent_id)

    # ── Initialize Hermes Runtime ──
    runtime = HermesRuntime(
        profile=profile_data,
        tools=profile_data.get("tools", []),
        memory=MemoryManager(agent_id),
    )

    # ── Subscribe to signals ──
    await pubsub.subscribe(channels.SIMULATION_TICK)
    await pubsub.subscribe(channels.agent_inbox(agent_id))

    # ── Ready ──
    await redis.publish(channels.AGENT_READY, agent_id)
    logger.info("[%s] 就绪，进入主循环", agent_id)

    # ── Main loop ──
    async for msg in pubsub.listen():
        if msg["type"] != "message":
            continue
        channel = msg["channel"]
        if channel == channels.SIMULATION_TICK:
            await handle_tick(runtime, redis, agent_id)
        elif channel == channels.agent_inbox(agent_id):
            await handle_message(runtime, json.loads(msg["data"]))

    # ── Shutdown ──
    await redis.publish(channels.AGENT_OFFLINE, agent_id)
    await pubsub.close()
    await redis.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
