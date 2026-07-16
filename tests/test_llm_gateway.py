"""LLM gateway tests.

mocked uses httpx.MockTransport, no real Key/network needed.
live tests only run when a real LLM_API_KEY is configured in the environment.
"""

from __future__ import annotations

import json
import os

import httpx
import pytest

from aisim.llm.provider import LLMError, OpenAICompatibleProvider
from aisim.shared.config import LLMConfig
from aisim.shared.models import AgentProfile, Personality

pytestmark = pytest.mark.asyncio


def _ok_handler(captured: dict | None = None, content: str = "hello world", total_tokens: int = 13):
    def handler(request: httpx.Request) -> httpx.Response:
        if captured is not None:
            captured["url"] = str(request.url)
            captured["auth"] = request.headers.get("authorization")
            captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "model": json.loads(request.content)["model"],
                "choices": [{"message": {"role": "assistant", "content": content}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 3, "total_tokens": total_tokens},
            },
        )

    return handler


# ── Provider ──


async def test_provider_request_and_parse():
    captured: dict = {}
    transport = httpx.MockTransport(_ok_handler(captured))
    provider = OpenAICompatibleProvider(
        api_key="sk-test", base_url="https://example.com/v1", transport=transport
    )
    resp = await provider.chat(
        model="gpt-4o-mini", system="sys", messages=[{"role": "user", "content": "hi"}]
    )
    assert captured["url"] == "https://example.com/v1/chat/completions"
    assert captured["auth"] == "Bearer sk-test"
    assert captured["body"]["model"] == "gpt-4o-mini"
    assert captured["body"]["messages"][0] == {"role": "system", "content": "sys"}
    assert resp.content == "hello world"
    assert resp.total_tokens() == 13
    await provider.aclose()


async def test_provider_http_error_raises():
    transport = httpx.MockTransport(lambda r: httpx.Response(401, text="unauthorized"))
    provider = OpenAICompatibleProvider(api_key="sk-bad", base_url="https://example.com/v1", transport=transport)
    with pytest.raises(LLMError):
        await provider.chat(model="gpt-4o-mini", system="s", messages=[])
    await provider.aclose()


async def test_provider_no_api_key_raises():
    provider = OpenAICompatibleProvider(api_key="", base_url="https://example.com/v1")
    with pytest.raises(LLMError):
        await provider.chat(model="m", system="s", messages=[])
    await provider.aclose()


# ── Gateway ──


def _gateway_with_mock(handler, routing=None):
    transport = httpx.MockTransport(handler)
    provider = OpenAICompatibleProvider(api_key="sk-test", base_url="https://example.com/v1", transport=transport)
    cfg = LLMConfig(api_key="sk-test", routing=routing or {})
    from aisim.llm.gateway import LLMGateway

    return LLMGateway(cfg, provider=provider)


async def test_gateway_chat_uses_provider_and_router():
    gw = _gateway_with_mock(_ok_handler(content="ok", total_tokens=5), routing={"junior-engineer": "gpt-4o-mini"})
    profile = AgentProfile(
        agent_id="eng-sam", name="Sam", role="junior-engineer", department="Engineering", personality=Personality()
    )
    resp = await gw.chat(profile, messages=[{"role": "user", "content": "hi"}])
    assert resp.content == "ok"
    assert resp.error is None
    assert gw.usage_today == 5
    await gw.aclose()


async def test_gateway_error_returns_error_response():
    gw = _gateway_with_mock(lambda r: httpx.Response(500, text="boom"))
    profile = AgentProfile(agent_id="x", name="X", role="ceo", department="Exec")
    resp = await gw.chat(profile, messages=[])
    assert resp.error is not None
    assert resp.content == ""
    await gw.aclose()


async def test_gateway_resolves_tools():
    captured: dict = {}
    gw = _gateway_with_mock(_ok_handler(captured))
    profile = AgentProfile(agent_id="c", name="C", role="ceo", department="Exec")
    await gw.chat(profile, messages=[], tools=["create_agent", "send_message"])
    assert "tools" in captured["body"]
    names = [t["function"]["name"] for t in captured["body"]["tools"]]
    assert "create_agent" in names
    assert "send_message" in names
    await gw.aclose()


async def test_budget_guard_stops_calls():
    from aisim.llm.gateway import LLMGateway
    from aisim.shared.config import LLMConfig

    gw = LLMGateway(LLMConfig(api_key="sk-test", daily_budget=100))
    gw.usage_today = 200  # over budget
    profile = AgentProfile(agent_id="x", name="X", role="ceo", department="E", personality=Personality())
    resp = await gw.chat(profile, [{"role": "user", "content": "hi"}], tools=None)
    assert resp.error is not None and "预算超限" in resp.error
    assert gw.usage_today == 200  # no new call, no increase
    await gw.aclose()


async def test_system_prompt_injects_skills():
    from aisim.llm.gateway import LLMGateway
    from aisim.shared.config import LLMConfig
    from aisim.shared.models import Skill, SkillCategory, SkillLevel, SkillStatus

    class FakeSkillPool:
        async def get_effective_skills(self, agent_id, role, dept):
            return [
                Skill(
                    id="s1", name="部署 Checklist", category=SkillCategory.OPERATIONS,
                    level=SkillLevel.ROLE, prompt_injection="部署前必跑全部测试",
                    status=SkillStatus.PUBLISHED,
                )
            ]

    gw = LLMGateway(LLMConfig(api_key="sk-test"))
    gw.skill_pool = FakeSkillPool()  # type: ignore[assignment]
    profile = AgentProfile(
        agent_id="e", name="E", role="senior-engineer",
        department="Engineering", personality=Personality(),
    )
    prompt = await gw._build_system_prompt(profile)
    assert "部署 Checklist" in prompt
    assert "部署前必跑全部测试" in prompt
    await gw.aclose()


# ── Live calls (requires LLM_API_KEY configured) ──


async def test_live_call():
    # explicit opt-in, to avoid accidental billing calls when .env auto-loads a real key during regular pytest.
    if os.environ.get("LLM_LIVE_TEST") not in ("1", "true", "yes"):
        pytest.skip("未启用真实调用 (设 LLM_LIVE_TEST=1 以运行)")
    key = os.environ.get("LLM_API_KEY")
    if not key or key == "sk-xxx":
        pytest.skip("未配置真实 LLM_API_KEY (跳过真实调用)")
    from aisim.llm.gateway import LLMGateway

    base = os.environ.get("LLM_BASE_URL", "")
    model = os.environ.get("LLM_MODEL", "gpt-4o-mini")
    gw = LLMGateway(
        LLMConfig(api_key=key, base_url=base, default_model=model,
                  routing={"junior-engineer": model, "default": model})
    )
    profile = AgentProfile(agent_id="t", name="T", role="junior-engineer", department="X")
    try:
        resp = await gw.chat(profile, messages=[{"role": "user", "content": "用一句中文说你好"}])
    finally:
        await gw.aclose()
    assert resp.error is None, resp.error
    assert resp.content, "空响应"
    print(f"\nLIVE model={resp.model} tokens={resp.total_tokens()} content={resp.content[:80]!r}")
