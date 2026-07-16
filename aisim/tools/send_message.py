"""send_message - inter-Agent communication (see §六 four communication modes)."""

from __future__ import annotations

from aisim.tools import BaseTool, register


class SendMessageTool(BaseTool):
    name = "send_message"
    description = "向其他 Agent 发送消息 (DM / 频道 / 广播公告)。"
    parameters = {
        "type": "object",
        "properties": {
            "recipient": {"type": "string", "description": "目标 agent_id (DM 时)"},
            "channel": {"type": "string", "description": "频道名 (频道消息时)"},
            "content": {"type": "string"},
            "content_type": {
                "type": "string",
                "enum": ["text", "code", "decision", "task", "feedback"],
            },
            "priority": {"type": "string", "enum": ["critical", "high", "normal", "low"]},
            "broadcast": {"type": "boolean", "description": "是否全体公告"},
        },
        "required": ["content"],
    }

    async def execute(self, **kwargs):  # type: ignore[override]
        # TODO: construct a Message and deliver it via MessageBus
        return {"status": "sent", "content": kwargs.get("content")}


register(SendMessageTool())
