"""Agent tool definitions (see §四 role-to-tool mapping table).

Each tool is a BaseTool subclass providing:
- name / description / parameters (JSON Schema style, for LLM function-calling)
- async execute(**kwargs) body

Tools are assigned per role (see aisim.company.profile_registry.TOOLS_BY_ROLE).
"""

from __future__ import annotations

from typing import Any


class BaseTool:
    """Tool base class."""

    name: str = ""
    description: str = ""
    parameters: dict[str, Any] = {}

    async def execute(self, **kwargs: Any) -> Any:
        raise NotImplementedError

    def as_function_schema(self) -> dict[str, Any]:
        """Convert to a tool description for LLM function-calling."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


# Tool registry (name -> instance), populated when each tool module is imported
_TOOLS: dict[str, BaseTool] = {}


def register(tool: BaseTool) -> BaseTool:
    _TOOLS[tool.name] = tool
    return tool


def get_tool(name: str) -> BaseTool | None:
    return _TOOLS.get(name)


def get_tools(names: list[str]) -> list[BaseTool]:
    """Fetch tool instances by a list of names (for Agent profile.tools)."""
    return [t for t in (_TOOLS.get(n) for n in names) if t is not None]


def all_tools() -> dict[str, BaseTool]:
    return dict(_TOOLS)


# Import each tool module to trigger registration
from aisim.tools import (  # noqa: E402,F401  registration side effect
    call_meeting,
    complete_task,
    create_agent,
    create_task,
    file_ops,
    learn_skill,
    send_message,
    share_skill,
    web_search,
)
