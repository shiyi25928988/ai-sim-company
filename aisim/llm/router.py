"""角色 -> 模型路由 (见 §七 routing)。

默认: 所有角色用 default_model (= LLM_MODEL)。仅当需要按角色差异化模型时，
在 config/company.yaml 的 llm.routing 里覆盖个别角色。这样单 OpenAI 兼容端点
(如 DeepSeek / 智谱 / one-api) 只需设 LLM_MODEL，全员用同一模型。
"""

from __future__ import annotations

from aisim.shared.config import LLMConfig


class ModelRouter:
    """按角色选模型; 未列出的角色回退到 default_model。"""

    def __init__(self, config: LLMConfig) -> None:
        self.default_model = config.default_model
        self.routing = dict(config.routing)

    def select(self, role: str) -> str:
        return self.routing.get(role, self.routing.get("default", self.default_model))

    def cheapest(self) -> str:
        """预算耗尽时回退到的最便宜模型 (用 default_model)。"""
        return self.default_model
