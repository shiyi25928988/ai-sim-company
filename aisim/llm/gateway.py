"""Unified LLM gateway - company-level LLM access (see §七).

Responsibilities:
1. Select model by role (router)
2. Budget check (fall back to the cheapest model when exceeded)
3. Dynamically assemble the System Prompt (identity + company context + Skills)
4. Call the provider (OpenAI compatible) and keep the books

The API Key is configured once in Company Hub; Agents are unaware which model serves them.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any

from aisim.llm.provider import LLMError, OpenAICompatibleProvider
from aisim.llm.router import ModelRouter
from aisim.shared.config import LLMConfig
from aisim.shared.models import AgentProfile

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    """LLM response."""

    content: str
    tool_calls: list[dict] | None = None
    usage: dict = field(default_factory=dict)
    error: str | None = None
    model: str = ""

    def total_tokens(self) -> int:
        return int((self.usage or {}).get("total_tokens", 0))


class LLMGateway:
    """Company-level LLM gateway. Agents carry no LLM config; all calls go through here."""

    def __init__(self, config: LLMConfig, provider: OpenAICompatibleProvider | None = None) -> None:
        self.config = config
        self.router = ModelRouter(config)
        self.daily_budget = config.daily_budget
        self.usage_today = 0
        # Provider is injectable (MockTransport for tests); otherwise created from config
        self.provider = provider or OpenAICompatibleProvider(
            api_key=config.api_key, base_url=config.base_url
        )
        # Company Skill Pool (injected by the Hub; injects Skills into the System Prompt)
        self.skill_pool = None
        # Concurrency limit to avoid LLM rate limits (429)
        self._sem = asyncio.Semaphore(2)
        # RPM rate limiting (token bucket algorithm; refill every 60s with rpm_limit tokens)
        # Guards: _lock must be held when updating _tokens/_last_refill (they are modified concurrently from multiple agent ticks)
        self._rpm_lock = asyncio.Lock()
        self._rpm_tokens = 0.0
        self._rpm_last_refill = 0.0

    async def _await_rate_limit(self) -> None:
        """RPM token bucket (RFC 7231 pattern). Returns when a token is available.

        Refills tokens lazily on each call based on elapsed time since last refill.
        No-op if rpm_limit <= 0 (rate limiting disabled)."""
        rpm = self.config.rpm_limit
        if rpm <= 0:
            return

        import time

        async with self._rpm_lock:
            now = time.monotonic()
            # 60s interval (RPM) - don't let "stale" refill (e.g. after long pause) overfill the bucket
            elapsed = now - self._rpm_last_refill
            if elapsed >= 60:
                self._rpm_tokens = float(rpm)
                self._rpm_last_refill = now
            else:
                self._rpm_tokens += rpm * elapsed / 60.0
                self._rpm_tokens = min(self._rpm_tokens, rpm)  # never overfill

            if self._rpm_tokens < 1:
                wait = (1.0 - self._rpm_tokens) / rpm * 60.0
                # release lock during sleep (so other coroutines refill concurrently)
                await asyncio.sleep(wait)
                self._rpm_tokens = max(0.0, self._rpm_tokens + rpm * wait / 60.0 - 1)
            else:
                self._rpm_tokens -= 1

    async def chat(
        self, agent_profile: AgentProfile, messages: list, tools: list | None = None
    ) -> LLMResponse:
        # 1. Select model by role
        model = self.router.select(agent_profile.role)

        # 2. Rate limit (RPM token bucket)
        await self._await_rate_limit()

        # 3. Hard budget cap: stop when exceeded (cost control, avoids runaway billing)
        if self.daily_budget > 0 and self.usage_today > self.daily_budget:
            logger.warning("LLM 预算超限: usage=%d > budget=%d，暂停调用", self.usage_today, self.daily_budget)
            return LLMResponse(
                content="",
                error=f"预算超限 (usage {self.usage_today} > budget {self.daily_budget})",
                model=model,
            )

        # 4. Assemble the System Prompt (identity + company context + Skills)
        system_prompt = await self._build_system_prompt(agent_profile)

        # 5. Tools -> OpenAI function schema (omitted entirely when the endpoint has no function-calling support)
        tool_schemas = self._resolve_tools(tools or []) if self.config.enable_tools else []

        # 6. Call the provider (concurrency-limited to avoid 429)
        async with self._sem:
            try:
                response = await self.provider.chat(
                    model=model, system=system_prompt, messages=messages, tools=tool_schemas
                )
            except LLMError as e:
                logger.error("LLM 调用失败 [%s]: %s", model, e)
                return LLMResponse(content="", error=str(e), model=model)

        # 7. Validate tool calls for obvious issues before returning
        if response.tool_calls:
            for tc in response.tool_calls:
                fn = tc.get("function", {}) if isinstance(tc, dict) else {}
                name = fn.get("name", "")
                raw_args = fn.get("arguments")
                if isinstance(raw_args, str):
                    try:
                        args = json.loads(raw_args)
                    except json.JSONDecodeError:
                        args = None
                else:
                    args = raw_args if isinstance(raw_args, dict) else None
                if args is None:
                    logger.warning("[%s] 工具调用参数非JSON: %s", model, raw_args)

        self.usage_today += response.total_tokens()
        response.model = response.model or model
        return response

    async def _build_system_prompt(self, profile: AgentProfile) -> str:
        """Dynamically assemble the System Prompt before each Agent LLM call (see §七/§八).

        First renders the role template prompts/{role}.j2 (identity + responsibilities + behavior constraints);
        then injects the prompt_injection of the Agent's effective Skills (company/department/role/personal).
        Live state (funds/team/tasks) is placed in the user message by the caller.
        """
        base = profile.system_prompt or self._render_role_template(profile)

        skill_text = ""
        if self.skill_pool is not None:
            skills = await self.skill_pool.get_effective_skills(
                profile.agent_id, profile.role, profile.department
            )
            if skills:
                skill_text = "\n\n".join(
                    f"## Skill: {s.name}\n{s.prompt_injection}" for s in skills
                )

        # Common thinking framework (Claude Code pattern) - applied to all agents
        thinking_framework = f"""

# How to Think and Act

## Step 1: Reason First
Before calling any tool, think through the situation:
1. What is the immediate priority? (Look at pending tasks first)
2. What information do I already have? What is missing?
3. What action will move the needle most right now?
4. What tool(s) do I need, and what parameters will they take?

Be specific and concise.

## Step 2: Tool Use Rules
- Call tools sequentially, NOT in parallel. One tool per turn.
- Read tool results carefully before deciding on the next action.
- If a tool fails: read the error message, fix the parameters, and retry ONCE. Do not loop infinitely.
- If you don't know exact parameters, look them up first (e.g. find_skill before learn_skill).
- For write_file / code: produce actual working content, not placeholders or TODOs.

## Step 3: Verify & Close
After you have acted and tool results are back:
1. Did the tool call succeed?
2. Is the task done? If yes, use complete_task with a clear result description.
3. If not, what's the next step?
4. When you have no further actions, reply with summary text to end the turn.

## Constraints
- Max 3 tool calls per turn. Finish quickly, produce visible output.
- Be concise. No long monologues - focus on action.
- Use send_message for coordination with other team members.
- You are autonomous. Do not wait for user input - decide and act.
"""

        return f"{base}{thinking_framework}\n\n{skill_text}".strip() if skill_text else f"{base}{thinking_framework}"

    def _render_role_template(self, profile: AgentProfile) -> str:
        """Render prompts/{role}.j2; fall back to the identity block on failure."""
        import os

        from aisim.agent.identity import build_identity_block

        try:
            from jinja2 import Environment, FileSystemLoader, TemplateNotFound
        except ImportError:
            return build_identity_block(profile)

        prompts_dir = os.path.join(os.path.dirname(__file__), "prompts")
        env = Environment(loader=FileSystemLoader(prompts_dir), autoescape=False)
        try:
            tmpl = env.get_template(f"{profile.role.replace('-', '_')}.j2")
        except TemplateNotFound:
            return build_identity_block(profile)
        return tmpl.render(profile=profile)

    def _resolve_tools(self, tools: list) -> list[dict]:
        """Normalize a tool list into OpenAI function-calling schemas.

        Accepts: BaseTool instances / dicts that are already schemas / tool names (str).
        """
        from aisim.tools import BaseTool, all_tools

        registry = all_tools()
        schemas: list[dict] = []
        for t in tools:
            if isinstance(t, BaseTool):
                schemas.append(t.as_function_schema())
            elif isinstance(t, dict):
                schemas.append(t)
            elif isinstance(t, str):
                tool = registry.get(t)
                if tool is not None:
                    schemas.append(tool.as_function_schema())
        return schemas

    async def aclose(self) -> None:
        await self.provider.aclose()
