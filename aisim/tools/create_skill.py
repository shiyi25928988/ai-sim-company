"""create_skill - an agent creates a new skill in the company pool (any level/scope)."""

from __future__ import annotations

from aisim.tools import BaseTool, register


class CreateSkillTool(BaseTool):
    name = "create_skill"
    description = (
        "Create a new skill in the company pool from distilled experience/knowledge. "
        "Published immediately; agents inherit it by level/scope."
    )
    parameters = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Skill name"},
            "prompt_injection": {
                "type": "string",
                "description": "The knowledge/rule injected into inheriting agents' system prompt",
            },
            "description": {"type": "string"},
            "category": {"type": "string", "enum": ["technical", "management", "creative", "operations"]},
            "level": {"type": "string", "enum": ["company", "department", "role", "personal"]},
            "scope": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Who inherits: empty for company; department name / role / agent_id for others",
            },
        },
        "required": ["name", "prompt_injection"],
    }

    async def execute(self, **kwargs):  # type: ignore[override]
        # Executed by SimulatedAgentRunner._execute_tool.
        return {"status": "created", "name": kwargs.get("name")}


register(CreateSkillTool())
