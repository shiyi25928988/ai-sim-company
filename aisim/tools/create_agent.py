"""create_agent - create a new Agent (available to CEO / HR Director, see §四).

Implementation: Company Hub starts a container via the Docker API + generates and pushes a Profile.
"""

from __future__ import annotations

from aisim.tools import BaseTool, register


class CreateAgentTool(BaseTool):
    name = "create_agent"
    description = "招聘并创建一个新 Agent 容器 (CEO/HR 专用)。"
    parameters = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "新 Agent 的名字"},
            "role": {
                "type": "string",
                "description": "角色: ceo/cto/hr-director/senior-engineer/junior-engineer/designer",
            },
            "department": {"type": "string", "description": "所属部门"},
            "salary": {"type": "integer", "description": "年薪 ($)"},
            "personality": {
                "type": "object",
                "description": "Big-5 人格特质 (O/C/E/A/N, 0~1)",
            },
        },
        "required": ["name", "role"],
    }

    async def execute(self, **kwargs):  # type: ignore[override]
        # TODO: profile_registry.generate_profile -> agent_manager.create_agent
        #       -> wait for report-in -> push Profile -> notify frontend -> deduct salary budget
        return {"status": "pending", "name": kwargs.get("name"), "role": kwargs.get("role")}


register(CreateAgentTool())
