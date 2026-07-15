"""Agent 工具定义 (见 §四 角色与工具对照表)。

每个工具是一个 BaseTool 子类，提供:
- name / description / parameters (JSON Schema 风格，供 LLM function-calling)
- async execute(**kwargs) 执行体

工具按角色分配 (见 aisim.company.profile_registry.TOOLS_BY_ROLE)。
"""

from __future__ import annotations

from typing import Any


class BaseTool:
    """工具基类。"""

    name: str = ""
    description: str = ""
    parameters: dict[str, Any] = {}

    async def execute(self, **kwargs: Any) -> Any:
        raise NotImplementedError

    def as_function_schema(self) -> dict[str, Any]:
        """转为 LLM function-calling 的工具描述。"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


# 工具注册表 (name -> 实例)，在各工具模块导入时填充
_TOOLS: dict[str, BaseTool] = {}


def register(tool: BaseTool) -> BaseTool:
    _TOOLS[tool.name] = tool
    return tool


def get_tool(name: str) -> BaseTool | None:
    return _TOOLS.get(name)


def get_tools(names: list[str]) -> list[BaseTool]:
    """按名字列表取出工具实例 (供 Agent profile.tools 使用)。"""
    return [t for t in (_TOOLS.get(n) for n in names) if t is not None]


def all_tools() -> dict[str, BaseTool]:
    return dict(_TOOLS)


# 导入各工具模块以触发注册
from aisim.tools import (  # noqa: E402,F401  注册副作用
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
