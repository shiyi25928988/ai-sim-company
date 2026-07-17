"""share_skill - a Senior distills experience into a Skill and publishes it to a role (see §八).

Creates a ROLE-level Skill in the company pool (scope=[target_role]); all agents of that role inherit it.
"""

from __future__ import annotations

from aisim.tools import BaseTool, register


class ShareSkillTool(BaseTool):
    name = "share_skill"
    description = (
        "Distill an experience/rule into a Skill and publish it to a role; all agents of that "
        "role inherit it (Senior -> Junior)."
    )
    parameters = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Skill name, e.g. 'Architecture review checklist'"},
            "prompt_injection": {
                "type": "string",
                "description": "The experience/rule text injected into the role's agent system prompt",
            },
            "target_role": {
                "type": "string",
                "description": "Target role: junior-engineer / senior-engineer / designer",
            },
        },
        "required": ["name", "prompt_injection", "target_role"],
    }

    async def execute(self, **kwargs):  # type: ignore[override]
        # Executed by SimulatedAgentRunner._execute_tool.
        return {"status": "shared", "name": kwargs.get("name")}


register(ShareSkillTool())
