"""SimulatedAgentRunner tests (including multi-turn tool loops).

Unit tests use FakeHub (no Redis/LLM), FakeGateway returns a set of responses in order to simulate multiple turns.
live tests require LLM_LIVE_TEST=1 + real key + Redis.
"""

from __future__ import annotations

import asyncio
import json
import os
from types import SimpleNamespace

import pytest

from aisim.company.agent_runner import SimulatedAgentRunner
from aisim.llm.gateway import LLMResponse
from aisim.shared.models import AgentProfile, Personality

pytestmark = pytest.mark.asyncio


def _profile() -> AgentProfile:
    return AgentProfile(
        agent_id="ceo-alex", name="Alex", role="ceo", department="Executive",
        personality=Personality(), tools=["create_agent", "send_message"],
    )


def _tc(name: str, args: dict) -> dict:
    """Construct a tool_call."""
    return {"id": name, "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}


class FakeGateway:
    """Returns a set of responses in order (simulating multi-turn LLM replies); after exhaustion returns a terminal reply with no tools."""

    def __init__(self, *responses: LLMResponse) -> None:
        self.responses = list(responses)
        self.calls: list[dict] = []

    async def chat(self, profile, messages, tools=None):
        self.calls.append({"profile": profile, "messages": messages, "tools": tools})
        if self.responses:
            return self.responses.pop(0)
        return LLMResponse(content="(done)", usage={"total_tokens": 0})


class FakeMessageBus:
    def __init__(self) -> None:
        self.dms: list = []
        self.broadcasts: list = []

    async def send_dm(self, sender, recipient, content):
        self.dms.append((sender, recipient, content))

    async def broadcast_announcement(self, sender, content):
        self.broadcasts.append((sender, content))


class FakeTaskManager:
    async def pending_for(self, agent_id, role):
        from aisim.shared.models import Task, TaskStatus
        return [Task(id="task-1-x", title="Test task", status=TaskStatus.PENDING, assignee="", assignee_role=role)]

    async def claim(self, task_id, agent_id):
        return None


class FakeAgentManager:
    async def set_status(self, agent_id, status):
        pass


class FakeHub:
    def __init__(self, *responses: LLMResponse) -> None:
        self.llm_gateway = FakeGateway(*responses)
        self.message_bus = FakeMessageBus()
        self.task_manager = FakeTaskManager()
        self.agent_manager = FakeAgentManager()
        self.config = SimpleNamespace(
            llm=SimpleNamespace(max_iters=3),
            simulation=SimpleNamespace(agent_think_every=1),
            company=SimpleNamespace(business_description="", monthly_budget=0),
        )
        self.mcp_manager = SimpleNamespace(list_all_tools=lambda: [])
        self.events: list[dict] = []
        self.created: list[dict] = []
        self.tasks: list[dict] = []
        self.completed: list[dict] = []
        self.shared: list[dict] = []
        self.learned: list[dict] = []
        self.meetings: list[dict] = []
        self._n = 0

    async def snapshot(self) -> dict:
        return {
            "tick": 7, "company": "TestCo",
            "economy": {"capital": 1000, "monthly_burn": 0, "revenue": 0, "bankrupt": False},
            "agents": [{"name": "Alex", "role": "ceo"}],
            "tasks": [],
        }

    async def emit_frontend(self, event: dict) -> None:
        self.events.append(event)

    async def create_agent(self, **kw) -> dict:
        self._n += 1
        self.created.append(kw)
        return {"agent_id": f"x{self._n}", "name": kw["name"], "role": kw["role"]}

    async def create_task(self, **kw) -> dict:
        self._n += 1
        rec = {"id": f"task{self._n}", "title": kw.get("title", ""), **kw}
        self.tasks.append(rec)
        return {"id": rec["id"], "title": rec["title"]}

    async def complete_task(self, task_id, agent_id, result) -> dict:
        self.completed.append({"task_id": task_id, "by": agent_id, "result": result})
        return {"task_id": task_id, "status": "done"}

    async def remove_agent(self, agent_id) -> dict:
        return {"removed": agent_id}

    async def share_skill(self, **kw) -> dict:
        self.shared.append(kw)
        return {"name": kw.get("name")}

    async def learn_skill(self, agent_id, query) -> dict:
        self.learned.append({"agent_id": agent_id, "query": query})
        return {"name": "学到的技能"}

    async def call_meeting(self, caller_id, topic, participants) -> str:
        self.meetings.append({"caller": caller_id, "topic": topic, "participants": participants})
        return "会议纪要: 决定招聘2名工程师。"


# ── Unit ──


async def test_tick_calls_gateway_with_prompt():
    hub = FakeHub(LLMResponse(content="我先招一名 HR 总监", usage={"total_tokens": 5}))
    runner = SimulatedAgentRunner(hub)
    runner.register(_profile())
    await runner._agent_tick("ceo-alex", await hub.snapshot())
    assert len(hub.llm_gateway.calls) == 1  # no tool_calls -> single turn ends
    msg = hub.llm_gateway.calls[0]["messages"][0]["content"]
    assert "Alex" in msg and "ceo" in msg
    assert any(e["type"] == "agent_message" for e in hub.events)


async def test_tick_executes_create_agent_tool_call():
    hub = FakeHub(
        LLMResponse(content="", tool_calls=[_tc("create_agent", {"name": "Taylor", "role": "hr-director", "salary": 120000})], usage={"total_tokens": 5}),
        LLMResponse(content="招到了", usage={"total_tokens": 1}),
    )
    runner = SimulatedAgentRunner(hub)
    runner.register(_profile())
    await runner._agent_tick("ceo-alex", await hub.snapshot())
    assert len(hub.created) == 1
    assert hub.created[0]["name"] == "Taylor"
    assert hub.created[0]["role"] == "hr-director"
    assert any("create_agent" in e.get("action", "") for e in hub.events)


async def test_tick_send_message_tool_uses_message_bus():
    hub = FakeHub(
        LLMResponse(content="", tool_calls=[_tc("send_message", {"recipient": "hr-taylor", "content": "开始招聘"})], usage={"total_tokens": 1}),
        LLMResponse(content="已发", usage={"total_tokens": 1}),
    )
    runner = SimulatedAgentRunner(hub)
    runner.register(_profile())
    await runner._agent_tick("ceo-alex", await hub.snapshot())
    assert len(hub.message_bus.dms) == 1
    assert hub.message_bus.dms[0][1] == "hr-taylor"


async def test_tick_create_task_dispatch():
    hub = FakeHub(
        LLMResponse(content="", tool_calls=[_tc("create_task", {"title": "搭 API", "assignee_role": "senior-engineer", "description": "写接口"})], usage={"total_tokens": 1}),
        LLMResponse(content="已派", usage={"total_tokens": 1}),
    )
    runner = SimulatedAgentRunner(hub)
    runner.register(_profile())
    await runner._agent_tick("ceo-alex", await hub.snapshot())
    assert len(hub.tasks) == 1
    assert hub.tasks[0]["title"] == "搭 API"


async def test_tick_complete_task_dispatch():
    hub = FakeHub(
        LLMResponse(content="", tool_calls=[_tc("complete_task", {"task_id": "task-1-x", "result": "写好了"})], usage={"total_tokens": 1}),
        LLMResponse(content="完成", usage={"total_tokens": 1}),
    )
    runner = SimulatedAgentRunner(hub)
    eng = AgentProfile(agent_id="eng-jordan", name="Jordan", role="senior-engineer",
                       department="Engineering", personality=Personality(), tools=["complete_task"])
    runner.register(eng)
    await runner._agent_tick("eng-jordan", await hub.snapshot())
    assert len(hub.completed) == 1
    assert hub.completed[0]["task_id"] == "task-1-x"


async def test_tick_share_skill_dispatch():
    hub = FakeHub(
        LLMResponse(content="", tool_calls=[_tc("share_skill", {"name": "架构审查规范", "prompt_injection": "审查关注正确性/边界", "target_role": "junior-engineer"})], usage={"total_tokens": 1}),
        LLMResponse(content="已分享", usage={"total_tokens": 1}),
    )
    runner = SimulatedAgentRunner(hub)
    sr = AgentProfile(agent_id="eng-jordan", name="Jordan", role="senior-engineer",
                      department="Engineering", personality=Personality(), tools=["share_skill"])
    runner.register(sr)
    await runner._agent_tick("eng-jordan", await hub.snapshot())
    assert len(hub.shared) == 1
    assert hub.shared[0]["target_role"] == "junior-engineer"


async def test_tick_learn_skill_dispatch():
    hub = FakeHub(
        LLMResponse(content="", tool_calls=[_tc("learn_skill", {"query": "单元测试"})], usage={"total_tokens": 1}),
        LLMResponse(content="已学习", usage={"total_tokens": 1}),
    )
    runner = SimulatedAgentRunner(hub)
    jr = AgentProfile(agent_id="eng-sam", name="Sam", role="junior-engineer",
                      department="Engineering", personality=Personality(), tools=["learn_skill"])
    runner.register(jr)
    await runner._agent_tick("eng-sam", await hub.snapshot())
    assert len(hub.learned) == 1
    assert hub.learned[0]["query"] == "单元测试"


async def test_tick_call_meeting_dispatch():
    hub = FakeHub(
        LLMResponse(content="", tool_calls=[_tc("call_meeting", {"topic": "Q2规划", "participants": ["ceo-alex", "hr-sarah"]})], usage={"total_tokens": 1}),
        LLMResponse(content="已开完会", usage={"total_tokens": 1}),
    )
    runner = SimulatedAgentRunner(hub)
    runner.register(_profile())
    await runner._agent_tick("ceo-alex", await hub.snapshot())
    assert len(hub.meetings) == 1
    assert hub.meetings[0]["topic"] == "Q2规划"
    assert "ceo-alex" in hub.meetings[0]["participants"]


async def test_multi_turn_chains_two_tools():
    """Within one tick, calls two tools in sequence (create_agent -> send_message), results fed back then ends."""
    hub = FakeHub(
        LLMResponse(content="", tool_calls=[_tc("create_agent", {"name": "Taylor", "role": "hr-director"})], usage={"total_tokens": 1}),
        LLMResponse(content="", tool_calls=[_tc("send_message", {"recipient": "hr-taylor", "content": "开始招聘"})], usage={"total_tokens": 1}),
        LLMResponse(content="都办好了", usage={"total_tokens": 1}),
    )
    runner = SimulatedAgentRunner(hub)
    runner.register(_profile())
    await runner._agent_tick("ceo-alex", await hub.snapshot())
    assert len(hub.created) == 1
    assert len(hub.message_bus.dms) == 1
    assert len(hub.llm_gateway.calls) == 3  # tool->tool->end
    # second turn's messages should contain the first turn's tool result
    msg_roles = [m["role"] for m in hub.llm_gateway.calls[1]["messages"]]
    assert "tool" in msg_roles


async def test_error_response_emits_action():
    hub = FakeHub(LLMResponse(content="", error="boom", usage={}))
    runner = SimulatedAgentRunner(hub)
    runner.register(_profile())
    await runner._agent_tick("ceo-alex", await hub.snapshot())
    assert any("LLM error" in e.get("action", "") for e in hub.events)
    assert len(hub.llm_gateway.calls) == 1  # stop on error


async def test_on_tick_skips_busy_agent():
    hub = FakeHub(LLMResponse(content="...", usage={"total_tokens": 1}))
    runner = SimulatedAgentRunner(hub)
    runner.register(_profile())
    await runner.start()
    runner._agents["ceo-alex"].busy = True
    await runner.on_tick(1)
    await asyncio.sleep(0.02)
    assert len(hub.llm_gateway.calls) == 0
    await runner.stop()


async def test_on_tick_dispatches_to_idle_agent():
    hub = FakeHub(LLMResponse(content="思考中", usage={"total_tokens": 1}))
    runner = SimulatedAgentRunner(hub)
    runner.register(_profile())
    await runner.start()
    await runner.on_tick(1)
    await asyncio.sleep(0.05)
    assert len(hub.llm_gateway.calls) == 1
    await runner.stop()


async def test_think_every_skips_off_ticks():
    hub = FakeHub(LLMResponse(content="...", usage={"total_tokens": 1}))
    hub.config.simulation.agent_think_every = 2
    runner = SimulatedAgentRunner(hub)
    runner.register(_profile())
    await runner.start()
    await runner.on_tick(1)  # 1 % 2 != 0 -> skip
    await asyncio.sleep(0.02)
    assert len(hub.llm_gateway.calls) == 0
    await runner.on_tick(2)  # 2 % 2 == 0 -> think
    await asyncio.sleep(0.05)
    assert len(hub.llm_gateway.calls) == 1
    await runner.stop()


async def test_recent_memory_records_thought():
    hub = FakeHub(LLMResponse(content="我在思考招人", usage={"total_tokens": 1}))
    runner = SimulatedAgentRunner(hub)
    runner.register(_profile())
    await runner._agent_tick("ceo-alex", await hub.snapshot())
    mem = runner.recent_memory("ceo-alex", 5)
    assert len(mem) >= 1
    assert any("我在思考招人" in m["content"] for m in mem)
    assert runner.recent_memory("unknown", 5) == []


async def test_run_tick_sequential_awaits_all_agents():
    """Single-step mode: multiple Agents execute sequentially and are awaited (not fire-and-forget)."""
    hub = FakeHub(
        LLMResponse(content="A思考", usage={"total_tokens": 1}),
        LLMResponse(content="B思考", usage={"total_tokens": 1}),
    )
    runner = SimulatedAgentRunner(hub)
    runner.register(AgentProfile(agent_id="a", name="A", role="ceo", department="E", personality=Personality(), tools=[]))
    runner.register(AgentProfile(agent_id="b", name="B", role="ceo", department="E", personality=Personality(), tools=[]))
    await runner.start()
    await runner.run_tick_sequential(1)
    # after sequential execution, both Agents have thought (no sleep needed)
    assert len(hub.llm_gateway.calls) == 2
    await runner.stop()


async def test_ceo_directive_delegates_hiring_to_hr():
    """PM-driven hiring: CEO hires HR -> HR hires PM -> PM raises hiring requests -> HR hires per request."""
    ceo = AgentProfile(agent_id="c", name="C", role="ceo", department="E", personality=Personality())
    # no HR -> CEO hires HR Director
    d0 = SimulatedAgentRunner._directive(ceo, [{"role": "ceo"}], [])
    assert "HR Director" in d0 and "create_agent" in d0
    # has HR, no PM -> CEO tells HR to hire a Product Manager
    d1 = SimulatedAgentRunner._directive(ceo, [{"role": "ceo"}, {"role": "hr-director"}], [])
    assert "Product Manager" in d1
    # HR perspective: no PM -> HR hires PM first
    hr = AgentProfile(agent_id="h", name="H", role="hr-director", department="People", personality=Personality())
    d2 = SimulatedAgentRunner._directive(hr, [{"role": "ceo"}, {"role": "hr-director"}], [])
    assert "Product Manager" in d2
    # HR with PM + a hiring-request task -> HR hires per request
    _T = type("T", (), {"id": "t1", "title": "Hiring request: need 1 senior-engineer - backend"})
    d3 = SimulatedAgentRunner._directive(
        hr,
        [{"role": "ceo"}, {"role": "hr-director"}, {"role": "product-manager"}],
        [_T()],
    )
    assert "hiring requests" in d3 and "create_agent" in d3


# ── Live calls (requires LLM_LIVE_TEST=1 + real key + Redis) ──


async def test_live_agent_tick():
    if os.environ.get("LLM_LIVE_TEST") not in ("1", "true", "yes"):
        pytest.skip("未启用真实调用 (设 LLM_LIVE_TEST=1)")
    key = os.environ.get("LLM_API_KEY")
    if not key or key == "sk-xxx":
        pytest.skip("无真实 LLM_API_KEY")
    if not (os.environ.get("REDIS_URL") or os.environ.get("REDIS_PASSWORD") or os.environ.get("REDIS_HOST")):
        pytest.skip("未配置 Redis")
    from aisim.company.hub import CompanyHub
    from aisim.shared import channels
    from aisim.shared.config import load_config

    cfg = load_config("config/company.yaml")
    hub = CompanyHub(cfg)
    events: list[dict] = []

    async def capture(ev: dict) -> None:
        events.append(ev)

    hub.on_frontend_event = capture
    await hub.start()
    await hub.clock.stop()  # avoid clock tick interference
    try:
        await hub.agent_runner._agent_tick("ceo-alex", await hub.snapshot())
        success = hub.llm_gateway.usage_today > 0
        print(f"\nLIVE success={success} usage={hub.llm_gateway.usage_today} events={len(events)}")
        for e in events[:5]:
            print("  ", e)
        assert success or any("LLM 错误" in e.get("action", "") for e in events)
    finally:
        await hub.message_bus.delete(
            channels.KEY_AGENTS, channels.KEY_PROFILES, channels.KEY_TASKS, channels.KEY_SKILLS
        )
        await hub.stop()
