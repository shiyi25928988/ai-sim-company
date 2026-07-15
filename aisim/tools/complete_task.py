"""complete_task - Agent 完成任务并汇报 (见 §三)。"""

from __future__ import annotations

from aisim.tools import BaseTool, register


class CompleteTaskTool(BaseTool):
    name = "complete_task"
    description = "完成一个分配给你的任务，并写明你做了什么。"
    parameters = {
        "type": "object",
        "properties": {
            "task_id": {"type": "string", "description": "任务 ID (见你的待办任务列表)"},
            "result": {"type": "string", "description": "完成汇报: 做了什么 / 产出 / 结论"},
        },
        "required": ["task_id", "result"],
    }

    async def execute(self, **kwargs):  # type: ignore[override]
        # TODO: 调 hub.complete_task
        return {"status": "done", "task_id": kwargs.get("task_id")}


register(CompleteTaskTool())
