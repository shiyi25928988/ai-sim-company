"""Meeting system tests - uses FakeGateway (no real LLM)."""

from __future__ import annotations

import pytest

from aisim.comm.meeting import MeetingSystem
from aisim.llm.gateway import LLMResponse
from aisim.shared.models import AgentProfile, Personality

pytestmark = pytest.mark.asyncio


class FakeGateway:
    def __init__(self, resp: LLMResponse) -> None:
        self.resp = resp
        self.calls: list[dict] = []

    async def chat(self, profile, messages, tools=None):
        self.calls.append({"profile": profile, "messages": messages, "tools": tools})
        return self.resp


async def test_meeting_run_produces_minutes():
    ms = MeetingSystem()
    meeting = ms.schedule("m1", "Q2 规划", ["ceo-alex", "hr-sarah"])
    gw = FakeGateway(LLMResponse(content="纪要: 决定招聘2名工程师，由HR负责。", usage={"total_tokens": 50}))
    host = AgentProfile(agent_id="ceo-alex", name="Alex", role="ceo", department="E", personality=Personality())
    parts = [{"name": "Alex", "role": "ceo"}, {"name": "Sarah", "role": "hr-director"}]

    minutes = await ms.run(meeting, parts, host, gw)

    assert "纪要" in minutes
    assert meeting.status == "ended"
    assert meeting.minutes == minutes
    assert len(gw.calls) == 1
    # prompt should contain topic and participants
    prompt = gw.calls[0]["messages"][0]["content"]
    assert "Q2 规划" in prompt and "Sarah" in prompt


async def test_meeting_run_handles_llm_error():
    ms = MeetingSystem()
    meeting = ms.schedule("m2", "故障复盘", ["a", "b"])
    gw = FakeGateway(LLMResponse(content="", error="boom", usage={}))
    host = AgentProfile(agent_id="a", name="A", role="ceo", department="E", personality=Personality())
    minutes = await ms.run(meeting, [{"name": "A", "role": "ceo"}], host, gw)
    assert "错误" in minutes
    assert meeting.status == "ended"
