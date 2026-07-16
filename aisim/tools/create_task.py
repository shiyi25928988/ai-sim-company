"""create_task - CEO/HR creates and dispatches a task (see §三 task decomposition and assignment)."""

from __future__ import annotations

from aisim.tools import BaseTool, register


class CreateTaskTool(BaseTool):
    name = "create_task"
    description = "创建一个工作任务并派发给某角色或具体 Agent。"
    parameters = {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "任务标题"},
            "description": {"type": "string", "description": "任务详情/验收标准"},
            "assignee_role": {
                "type": "string",
                "description": "派给某角色的任一 Agent: senior-engineer/junior-engineer/designer",
            },
            "assignee": {"type": "string", "description": "直接派给某 agent_id (与 assignee_role 二选一)"},
            "project": {"type": "string", "description": "所属项目"},
            "priority": {"type": "string", "enum": ["low", "normal", "high"]},
        },
        "required": ["title"],
    }

    async def execute(self, **kwargs):  # type: ignore[override]
        # TODO: call hub.create_task
        return {"status": "pending", "title": kwargs.get("title")}


register(CreateTaskTool())
