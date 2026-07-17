"""find_skill - search the company skill pool by keyword (no copy created)."""

from __future__ import annotations

from aisim.tools import BaseTool, register


class FindSkillTool(BaseTool):
    name = "find_skill"
    description = (
        "Search the company skill pool by keyword. Returns matching skills "
        "(name/level/scope/description/prompt) without creating a copy - use this to "
        "discover available knowledge before deciding to learn or apply it."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search keyword, e.g. 'deployment' / 'testing'"},
        },
        "required": ["query"],
    }

    async def execute(self, **kwargs):  # type: ignore[override]
        # Executed by SimulatedAgentRunner._execute_tool.
        return {"status": "ok", "query": kwargs.get("query")}


register(FindSkillTool())
