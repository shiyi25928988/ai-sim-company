"""Role -> model routing (see §七 routing).

Default: all roles use default_model (= LLM_MODEL). Only when you need to differentiate models by role,
override individual roles in llm.routing of config/company.yaml. This way a single OpenAI-compatible endpoint
(e.g. DeepSeek / Zhipu / one-api) only needs LLM_MODEL, and everyone uses the same model.
"""

from __future__ import annotations

from aisim.shared.config import LLMConfig


class ModelRouter:
    """Select model by role; unlisted roles fall back to default_model."""

    def __init__(self, config: LLMConfig) -> None:
        self.default_model = config.default_model
        self.routing = dict(config.routing)

    def select(self, role: str) -> str:
        return self.routing.get(role, self.routing.get("default", self.default_model))

    def cheapest(self) -> str:
        """The cheapest model to fall back to when the budget is exhausted (uses default_model)."""
        return self.default_model
