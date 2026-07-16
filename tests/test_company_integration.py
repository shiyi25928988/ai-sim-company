"""Company Hub integration tests - requires real Redis.

Skip condition: redis not installed, or REDIS_URL / REDIS_HOST+REDIS_PASSWORD not set.
Run example:
    REDIS_HOST=localhost REDIS_PASSWORD=123456 pytest tests/test_company_integration.py -q
"""

from __future__ import annotations

import os

import pytest

# The whole module depends on redis; skip all if not installed.
pytest.importorskip("redis")

import aisim  # noqa: E402,F401  triggers aisim/__init__.py to auto-load .env (REDIS config)

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
    # Clear persisted Hub state so _restore_state doesn't pick up a stale monthly_burn from a prior run.
    h.db.connect()
    h.db.delete("hub_state")
    h.db.close()
    yield h, channels  # synchronous yield; start/stop controlled explicitly in each test


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
        # economy should have accounted for the salary
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
        assert snap["running"] is False  # paused by default (SIM_AUTO_START=false)
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
    """After Hub restart, Agents in Redis should be re-registered to the runner (resume thinking)."""
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
        await h.stop()  # do not clear Redis, keep Agents for restart recovery

    # restart: new Hub, Redis still has CEO + Jordan
    cfg = load_config("config/company.yaml")
    h2 = CompanyHub(cfg)
    await h2.start()
    try:
        # _rehydrate_agents should register both CEO and Jordan back to the runner
        assert h2.agent_runner.has(h2.config.ceo.agent_id)
        assert state is not None
        assert h2.agent_runner.has(state["agent_id"])
    finally:
        await h2.message_bus.delete(ch.KEY_AGENTS, ch.KEY_PROFILES, ch.KEY_TASKS, ch.KEY_SKILLS)
        await h2.stop()
