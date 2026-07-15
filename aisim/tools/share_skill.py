"""share_skill - Senior 把经验提炼成 Skill 发布给某角色 (见 §八)。

落地: 在公司池创建一个 ROLE 级 Skill (scope=[target_role])，该角色全员自动继承。
"""

from __future__ import annotations

from aisim.tools import BaseTool, register


class ShareSkillTool(BaseTool):
    name = "share_skill"
    description = "把一条经验/规范提炼成 Skill 发布给某角色，该角色全员继承 (Senior -> Junior)。"
    parameters = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Skill 名，如 '架构审查规范'"},
            "prompt_injection": {
                "type": "string",
                "description": "注入到该角色 Agent System Prompt 的经验/规范正文",
            },
            "target_role": {
                "type": "string",
                "description": "目标角色: junior-engineer / senior-engineer / designer",
            },
        },
        "required": ["name", "prompt_injection", "target_role"],
    }

    async def execute(self, **kwargs):  # type: ignore[override]
        # TODO: 调 hub.share_skill
        return {"status": "shared", "name": kwargs.get("name")}


register(ShareSkillTool())
