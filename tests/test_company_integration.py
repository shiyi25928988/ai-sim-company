"""Company Hub 集成测试 - 需要真实 Redis。

跳过条件: 未安装 redis，或未设置 REDIS_URL / REDIS_HOST+REDIS_PASSWORD。
运行示例:
    REDIS_HOST=localhost REDIS_PASSWORD=123456 pytest tests/test_company_integration.py -q
"""

from __future__ import annotations

import os

import pytest

# 整个模块依赖 redis; 未安装则全部跳过。
pytest.importorskip("redis")

import aisim  # noqa: E402,F401  触发 aisim/__init__.py 自动加载 .env (REDIS 配置)

pytestmark = pytest.mark.asyncio


def _redis_configured() -> bool:
    return bool(
        os.environ.get("REDIS_URL")
        or os.environ.get("REDIS_PASSWORD")
        or os.environ.get("REDIS_HOST")
    )


@pytest.fixture
def hub():
    if not _redis_configured():
        pytest.skip("未配置 Redis (设置 REDIS_HOST/REDIS_PASSWORD 或 REDIS_URL)")
    from aisim.company.hub import CompanyHub
    from aisim.shared import channels
    from aisim.shared.config import load_config

    cfg = load_config("config/company.yaml")
    h = CompanyHub(cfg)
    yield h, channels  # 同步 yield; start/stop 在每个用例内显式控制


async def test_ceo_seeded(hub):
    h, ch = hub
    await h.start()
    try:
        ceo = await h.agent_manager.get(h.config.ceo.agent_id)
        assert ceo is not None
        assert ceo["role"] == "ceo"
        assert ceo["status"] == "ready"
    finally:
        await h.message_bus.delete(ch.KEY_AGENTS, ch.KEY_PROFILES, ch.KEY_TASKS)
        await h.stop()


async def test_create_and_list_agent(hub):
    h, ch = hub
    await h.start()
    try:
        state = await h.create_agent(
            name="Jordan", role="senior-engineer", department="Engineering", salary=130000
        )
        assert state["name"] == "Jordan"
        assert state["role"] == "senior-engineer"
        agents = await h.agent_manager.list()
        ids = [a["agent_id"] for a in agents]
        assert state["agent_id"] in ids
        # 经济系统应已计入薪资
        assert h.economy.state.monthly_burn == 130000
    finally:
        await h.message_bus.delete(ch.KEY_AGENTS, ch.KEY_PROFILES, ch.KEY_TASKS)
        await h.stop()


async def test_snapshot_shape(hub):
    h, ch = hub
    await h.start()
    try:
        snap = await h.snapshot()
        assert "economy" in snap
        assert "capital" in snap["economy"]
        assert isinstance(snap["agents"], list)
        assert snap["running"] is False  # 默认暂停 (SIM_AUTO_START=false)
    finally:
        await h.message_bus.delete(ch.KEY_AGENTS, ch.KEY_PROFILES, ch.KEY_TASKS)
        await h.stop()


async def test_remove_agent(hub):
    h, ch = hub
    await h.start()
    try:
        state = await h.create_agent(name="Sam", role="junior-engineer", salary=75000)
        await h.remove_agent(state["agent_id"])
        assert await h.agent_manager.get(state["agent_id"]) is None
        assert h.economy.state.monthly_burn == 0
    finally:
        await h.message_bus.delete(ch.KEY_AGENTS, ch.KEY_PROFILES, ch.KEY_TASKS)
        await h.stop()


async def test_rehydrate_agents_after_restart(hub):
    """Hub 重启后，Redis 里的 Agent 应被重新注册到 runner (恢复思考)。"""
    from aisim.company.hub import CompanyHub
    from aisim.shared.config import load_config

    h, ch = hub
    await h.start()
    state = None
    try:
        state = await h.create_agent(
            name="Jordan", role="senior-engineer", department="Engineering", salary=130000
        )
        assert h.agent_runner.has(state["agent_id"])
    finally:
        await h.stop()  # 不清 Redis，保留 Agent 供重启恢复

    # 重启: 新 Hub，Redis 里还有 CEO + Jordan
    cfg = load_config("config/company.yaml")
    h2 = CompanyHub(cfg)
    await h2.start()
    try:
        # _rehydrate_agents 应把 CEO + Jordan 都注册回 runner
        assert h2.agent_runner.has(h2.config.ceo.agent_id)
        assert state is not None
        assert h2.agent_runner.has(state["agent_id"])
    finally:
        await h2.message_bus.delete(ch.KEY_AGENTS, ch.KEY_PROFILES, ch.KEY_TASKS, ch.KEY_SKILLS)
        await h2.stop()
