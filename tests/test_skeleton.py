"""骨架冒烟测试 - 验证核心契约可导入且自洽。

刻意只覆盖无外部依赖 (redis / fastapi / hermes / pyyaml) 的模块，
保证在依赖未安装时仍能运行 `pytest`。
"""

from __future__ import annotations

import asyncio

import pytest

from aisim.shared import channels
from aisim.shared.models import (
    AgentProfile,
    AgentStatus,
    Message,
    MessageType,
    Personality,
    Skill,
    SkillCategory,
    SkillLevel,
    SkillStatus,
    personality_from_dict,
)
from aisim.simulation.clock import SimulationClock
from aisim.simulation.economy import EconomyEngine
from aisim.simulation.event_bus import EventBus, SimEvent
from aisim.company.org_chart import OrgChart
from aisim.agent.memory import MemoryManager, MemoryEntry
from aisim.skills.preset import PRESET_SKILLS


def test_personality_from_dict_tolerant():
    # Big-5 简写 key (LLM 常返回) + 多余字段
    p = personality_from_dict({"O": 0.9, "C": 0.8, "E": 0.7, "A": 0.6, "N": 0.3, "extra": 1})
    assert p.openness == 0.9
    assert p.neuroticism == 0.3
    # 全名 key
    p2 = personality_from_dict({"openness": 0.5, "conscientiousness": 0.4})
    assert p2.openness == 0.5 and p2.conscientiousness == 0.4
    # None / 非法值回退默认
    assert personality_from_dict(None) == Personality()
    assert personality_from_dict({"openness": "not-a-number"}).openness == 0.5


# ── 共享模型 ──


def test_agent_profile_defaults():
    p = AgentProfile(agent_id="eng-jordan", name="Jordan", role="senior-engineer", department="Engineering")
    assert p.status == AgentStatus.BOOTING
    assert p.energy == 100.0
    assert p.tools == []
    assert p.workspace == ""


def test_skill_enums_roundtrip():
    s = Skill(
        id="s1",
        name="部署 Checklist",
        category=SkillCategory.OPERATIONS,
        level=SkillLevel.COMPANY,
    )
    assert s.status == SkillStatus.DRAFT
    assert s.version == 1
    assert SkillCategory.OPERATIONS.value == "operations"


def test_message_types():
    m = Message(
        id="m1",
        type=MessageType.DM,
        sender="ceo-alex",
        recipients=["hr-taylor"],
        content="招个工程师",
    )
    assert m.type == MessageType.DM


# ── 通道命名 ──


def test_channel_helpers():
    assert channels.SIMULATION_TICK == "simulation:tick"
    assert channels.agent_inbox("eng-jordan") == "agent:eng-jordan:inbox"
    assert channels.agent_profile("ceo-alex") == "agent:ceo-alex:profile"
    assert channels.AGENT_REGISTER == "agent:register"


# ── 仿真: 时钟 / 经济 / 事件 ──


@pytest.mark.asyncio
async def test_clock_ticks():
    clock = SimulationClock(interval_ms=10)
    ticks: list[int] = []

    async def on_tick(t: int) -> None:
        ticks.append(t)

    clock.on_tick = on_tick
    await clock.start()
    await asyncio.sleep(0.05)
    await clock.stop()
    assert len(ticks) >= 1


def test_economy_salary_and_snapshot():
    eco = EconomyEngine(initial_capital=100_000)
    eco.add_salary(8_000)
    eco.apply_tick(tick=1)
    snap = eco.snapshot()
    assert snap["monthly_burn"] == 8_000
    assert snap["bankrupt"] is False


def test_event_bus_drain():
    bus = EventBus()
    seen: list[SimEvent] = []
    bus.subscribe(seen.append)
    bus.schedule(SimEvent(id="e1", kind="market", description="牛市"))
    drained = bus.drain()
    assert len(drained) == 1
    assert len(seen) == 1


# ── 组织架构 ──


def test_org_chart_reports():
    org = OrgChart()
    org.add("ceo-alex", "ceo", "Executive")
    org.add("hr-taylor", "hr-director", "People", reports_to="ceo-alex")
    assert org.direct_reports("ceo-alex") == ["hr-taylor"]
    assert org.get("hr-taylor").reports_to == "ceo-alex"
    org.remove("hr-taylor")
    assert org.direct_reports("ceo-alex") == []


# ── Agent 记忆 ──


def test_memory_recall():
    mem = MemoryManager("eng-jordan")
    mem.add(MemoryEntry(id="1", content="部署成功", importance=0.9))
    mem.add(MemoryEntry(id="2", content="修复 bug", importance=0.5))
    recent = mem.recent()
    assert len(recent) == 2
    assert recent[-1].content == "修复 bug"


# ── 预设 Skills ──


def test_preset_skills_for_engineer():
    skills = PRESET_SKILLS.get("senior-engineer", [])
    names = [s.name for s in skills]
    assert "Python 开发" in names
    assert all(s.status == SkillStatus.PUBLISHED for s in skills)


# ── 工具注册 (导入 aisim.tools 触发全部注册) ──


def test_tools_registered():
    from aisim.tools import all_tools

    tools = all_tools()
    for expected in [
        "create_agent",
        "send_message",
        "call_meeting",
        "write_file",
        "read_file",
        "list_files",
        "web_search",
        "share_skill",
        "learn_skill",
    ]:
        assert expected in tools, f"missing tool: {expected}"

    schema = tools["create_agent"].as_function_schema()
    assert schema["function"]["name"] == "create_agent"
