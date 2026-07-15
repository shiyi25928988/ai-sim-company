"""learn_skill - Junior 主动从公司池搜索并学习一个 Skill (见 §八)。"""

from __future__ import annotations

from aisim.tools import BaseTool, register


class LearnSkillTool(BaseTool):
    name = "learn_skill"
    description = "从公司 Skill 池按关键词搜索并学习一个 Skill (加入个人技能)。"
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "搜索关键词，如 '单元测试' / '部署'"},
        },
        "required": ["query"],
    }

    async def execute(self, **kwargs):  # type: ignore[override]
        # TODO: 调 hub.learn_skill
        return {"status": "ok", "query": kwargs.get("query")}


register(LearnSkillTool())
