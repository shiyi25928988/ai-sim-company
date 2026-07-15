"""LLM 统一网关 - 公司级 LLM 接入 (见 §七)。

职责:
1. 按角色选模型 (router)
2. 预算检查 (超额回退最便宜模型)
3. 动态组装 System Prompt (身份 + 公司上下文 + Skills)
4. 调用 provider (OpenAI 兼容) 并记账

API Key 只在 Company Hub 配一次; Agent 不感知自己用什么模型。
"""

from __future__ import annotations

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
    """LLM 返回。"""

    content: str
    tool_calls: list[dict] | None = None
    usage: dict = field(default_factory=dict)
    error: str | None = None
    model: str = ""

    def total_tokens(self) -> int:
        return int((self.usage or {}).get("total_tokens", 0))


class LLMGateway:
    """公司级 LLM 网关。Agent 不携带 LLM 配置，调用全部走这里。"""

    def __init__(self, config: LLMConfig, provider: OpenAICompatibleProvider | None = None) -> None:
        self.config = config
        self.router = ModelRouter(config)
        self.daily_budget = config.daily_budget
        self.usage_today = 0
        # 可注入 provider (测试用 MockTransport); 否则按 config 创建
        self.provider = provider or OpenAICompatibleProvider(
            api_key=config.api_key, base_url=config.base_url
        )
        # 公司 Skill Pool (由 Hub 注入; 注入 Skills 到 System Prompt)
        self.skill_pool = None

    async def chat(
        self, agent_profile: AgentProfile, messages: list, tools: list | None = None
    ) -> LLMResponse:
        # 1. 按角色选模型
        model = self.router.select(agent_profile.role)

        # 2. 预算硬上限: 超限即停 (控成本，避免失控计费)
        if self.daily_budget > 0 and self.usage_today > self.daily_budget:
            logger.warning("LLM 预算超限: usage=%d > budget=%d，暂停调用", self.usage_today, self.daily_budget)
            return LLMResponse(
                content="",
                error=f"预算超限 (usage {self.usage_today} > budget {self.daily_budget})",
                model=model,
            )

        # 3. 组装 System Prompt (身份 + 公司上下文 + Skills)
        system_prompt = await self._build_system_prompt(agent_profile)

        # 4. 工具 -> OpenAI function schema (端点不支持 function-calling 时整体不发)
        tool_schemas = self._resolve_tools(tools or []) if self.config.enable_tools else []

        # 5. 调用 provider
        try:
            response = await self.provider.chat(
                model=model, system=system_prompt, messages=messages, tools=tool_schemas
            )
        except LLMError as e:
            logger.error("LLM 调用失败 [%s]: %s", model, e)
            return LLMResponse(content="", error=str(e), model=model)

        self.usage_today += response.total_tokens()
        response.model = response.model or model
        return response

    async def _build_system_prompt(self, profile: AgentProfile) -> str:
        """每次 Agent 调 LLM 前，动态组装 System Prompt (见 §七/§八)。

        优先渲染角色模板 prompts/{role}.j2 (身份 + 职责 + 行为约束)；
        再注入该 Agent 生效的 Skills (company/department/role/personal) 的 prompt_injection。
        实时状态 (资金/团队/任务) 由调用方放在 user message 里。
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

        return f"{base}\n\n{skill_text}".strip() if skill_text else base

    def _render_role_template(self, profile: AgentProfile) -> str:
        """渲染 prompts/{role}.j2；失败则回退到 identity block。"""
        import os

        from aisim.agent.identity import build_identity_block

        try:
            from jinja2 import Environment, FileSystemLoader, TemplateNotFound
        except ImportError:
            return build_identity_block(profile)

        prompts_dir = os.path.join(os.path.dirname(__file__), "prompts")
        env = Environment(loader=FileSystemLoader(prompts_dir), autoescape=False)
        try:
            tmpl = env.get_template(f"{profile.role}.j2")
        except TemplateNotFound:
            return build_identity_block(profile)
        return tmpl.render(profile=profile)

    def _resolve_tools(self, tools: list) -> list[dict]:
        """把工具列表归一为 OpenAI function-calling schema。

        接受: BaseTool 实例 / 已是 schema 的 dict / 工具名 (str)。
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
