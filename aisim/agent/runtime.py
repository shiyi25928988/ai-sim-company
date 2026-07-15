"""Agent 运行时主程序 - 在每个 Agent 容器内运行 (见 §五)。

启动流程: 连接 Redis -> 报到 -> 等待 Profile -> 初始化 Hermes ->
就绪 -> Tick 主循环。身份 100% 由 Company Hub 通过 Redis 下发，
容器自身只认 REDIS_URL 与 AGENT_ID。

注: 使用 redis.asyncio (即文档中 aioredis 的继任者)。
"""

from __future__ import annotations

import asyncio
import json
import logging

from redis.asyncio import Redis

from aisim.agent.memory import MemoryManager
from aisim.shared import channels

logger = logging.getLogger(__name__)

# Hermes Agent (Nous Research) - 工具循环 / 记忆 / 技能 / LLM 抽象。
# 该包仅在 Agent 容器内可用; Hub 侧不应导入本模块。
from hermes import HermesRuntime  # type: ignore[import-not-found]  # noqa: E402


async def wait_for_message(pubsub) -> dict:
    """阻塞等待下一条 Pub/Sub 消息并解析为 dict。"""
    async for msg in pubsub.listen():
        if msg["type"] == "message":
            return json.loads(msg["data"])
    raise RuntimeError("pubsub closed before a message arrived")


async def handle_tick(runtime: HermesRuntime, redis: Redis, agent_id: str) -> None:
    """每 Tick: 检查 inbox -> Hermes.decide() (走 Hub LLM Gateway) -> 执行 -> 汇报。"""
    # TODO: 通过 hub:action 上报决策与执行结果; 同步 Skills 到公司池; 心跳。
    logger.debug("[%s] tick", agent_id)


async def handle_message(runtime: HermesRuntime, message: dict) -> None:
    """处理收件箱消息 (agent:{id}:inbox)。"""
    logger.debug("[%s] message: %s", runtime, message)


async def main() -> None:
    import os

    agent_id = os.environ["AGENT_ID"]
    redis_url = os.environ["REDIS_URL"]
    redis = Redis.from_url(redis_url, decode_responses=True)
    pubsub = redis.pubsub()

    # ── 报到 ──
    await redis.publish(
        channels.AGENT_REGISTER,
        json.dumps({"agent_id": agent_id, "status": "booting"}),
    )

    # ── 等待 Profile ──
    await pubsub.subscribe(channels.agent_profile(agent_id))
    profile_data = await wait_for_message(pubsub)
    logger.info("[%s] 收到 Profile", agent_id)

    # ── 初始化 Hermes Runtime ──
    runtime = HermesRuntime(
        profile=profile_data,
        tools=profile_data.get("tools", []),
        memory=MemoryManager(agent_id),
    )

    # ── 订阅信号 ──
    await pubsub.subscribe(channels.SIMULATION_TICK)
    await pubsub.subscribe(channels.agent_inbox(agent_id))

    # ── 就绪 ──
    await redis.publish(channels.AGENT_READY, agent_id)
    logger.info("[%s] 就绪，进入主循环", agent_id)

    # ── 主循环 ──
    async for msg in pubsub.listen():
        if msg["type"] != "message":
            continue
        channel = msg["channel"]
        if channel == channels.SIMULATION_TICK:
            await handle_tick(runtime, redis, agent_id)
        elif channel == channels.agent_inbox(agent_id):
            await handle_message(runtime, json.loads(msg["data"]))

    # ── 关闭 ──
    await redis.publish(channels.AGENT_OFFLINE, agent_id)
    await pubsub.close()
    await redis.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
