"""learn_skill - a Junior searches the company pool and learns a Skill (personal copy)."""

from __future__ import annotations

from aisim.tools import BaseTool, register


class LearnSkillTool(BaseTool):
    name = "learn_skill"
    description = (
        "Search the company skill pool by keyword and learn a matching skill "
        "(adds a personal copy to your own skills)."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search keyword, e.g. 'unit testing' / 'deployment'"},
        },
        "required": ["query"],
    }

    async def execute(self, **kwargs):  # type: ignore[override]
        # Executed by SimulatedAgentRunner._execute_tool.
        return {"status": "ok", "query": kwargs.get("query")}


register(LearnSkillTool())
