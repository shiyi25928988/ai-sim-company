"""会议系统 - LLM 主持 + 自动纪要 (见 §六 Meeting N:N)。

单次 LLM 调用: LLM 扮演主持人，让每位参会者 (按角色) 发言，最后输出纪要
(决议 / 待办 / 负责人)。纪要广播给参会者并推前端。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class Meeting:
    """一次会议 (N:N，由 LLM 主持)。"""

    id: str
    topic: str
    participants: list[str] = field(default_factory=list)  # agent_id 列表
    transcript: list[dict] = field(default_factory=list)
    minutes: str = ""
    status: str = "scheduled"  # scheduled | ongoing | ended


class MeetingSystem:
    """会议调度与 LLM 主持。"""

    def __init__(self) -> None:
        self._meetings: dict[str, Meeting] = {}

    def schedule(self, meeting_id: str, topic: str, participants: list[str]) -> Meeting:
        meeting = Meeting(id=meeting_id, topic=topic, participants=list(participants))
        self._meetings[meeting_id] = meeting
        logger.info("会议已安排: %s (参与 %d 人)", topic, len(participants))
        return meeting

    def get(self, meeting_id: str) -> Meeting | None:
        return self._meetings.get(meeting_id)

    async def run(self, meeting, participants_info, host_profile, llm_gateway) -> str:
        """LLM 主持整场会议并产出纪要 (单次调用)。"""
        prompt = self._build_prompt(meeting.topic, participants_info)
        meeting.status = "ongoing"
        try:
            resp = await llm_gateway.chat(
                host_profile, [{"role": "user", "content": prompt}], tools=[]
            )
            meeting.minutes = resp.content or "(无纪要)"
            if resp.error:
                meeting.minutes = f"(会议 LLM 错误: {resp.error})"
        except Exception as e:  # noqa: BLE001
            logger.exception("会议 LLM 调用失败")
            meeting.minutes = f"(会议失败: {e})"
        meeting.status = "ended"
        logger.info("会议结束: %s", meeting.topic)
        return meeting.minutes

    @staticmethod
    def _build_prompt(topic: str, participants_info: list[dict]) -> str:
        """渲染 meeting.j2; jinja2/模板缺失时回退内联。"""
        try:
            from jinja2 import Environment, FileSystemLoader

            prompts_dir = Path(__file__).parent.parent / "llm" / "prompts"
            env = Environment(loader=FileSystemLoader(str(prompts_dir)), autoescape=False)
            tmpl = env.get_template("meeting.j2")
            return tmpl.render(topic=topic, participants=participants_info)
        except Exception:  # noqa: BLE001
            parts = ", ".join(f"{p['name']}({p['role']})" for p in participants_info)
            return (
                f"你正在主持一场会议。\n主题: {topic}\n参会者: {parts}\n"
                "依次让参会者发言并输出纪要 (决议/待办/负责人)。"
            )
