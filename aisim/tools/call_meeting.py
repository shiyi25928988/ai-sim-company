"""call_meeting - start a meeting (see §六 Meeting N:N)."""

from __future__ import annotations

from aisim.tools import BaseTool, register


class CallMeetingTool(BaseTool):
    name = "call_meeting"
    description = "召集若干 Agent 开会 (LLM 主持，产出纪要)。"
    parameters = {
        "type": "object",
        "properties": {
            "topic": {"type": "string"},
            "participants": {
                "type": "array",
                "items": {"type": "string"},
                "description": "参会 agent_id 列表",
            },
        },
        "required": ["topic", "participants"],
    }

    async def execute(self, **kwargs):  # type: ignore[override]
        # TODO: MeetingSystem.schedule -> notify frontend meeting_start -> run
        return {
            "status": "scheduled",
            "topic": kwargs.get("topic"),
            "participants": kwargs.get("participants", []),
        }


register(CallMeetingTool())
