"""Meeting system - LLM-hosted with auto minutes (see §6 Meeting N:N).

A single LLM call: the LLM plays the host, lets each participant speak (by role),
and finally outputs minutes (decisions / action items / owners). Minutes are
broadcast to participants and pushed to the frontend.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class Meeting:
    """A single meeting (N:N, hosted by LLM)."""

    id: str
    topic: str
    participants: list[str] = field(default_factory=list)  # list of agent_ids
    transcript: list[dict] = field(default_factory=list)
    minutes: str = ""
    status: str = "scheduled"  # scheduled | ongoing | ended


class MeetingSystem:
    """Meeting scheduling and LLM hosting."""

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
        """Host the entire meeting via LLM and produce minutes (single call)."""
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
        """Render meeting.j2; fall back to inline prompt if jinja2/template is missing."""
        try:
            from jinja2 import Environment, FileSystemLoader

            prompts_dir = Path(__file__).parent.parent / "llm" / "prompts"
            env = Environment(loader=FileSystemLoader(str(prompts_dir)), autoescape=False)
            tmpl = env.get_template("meeting.j2")
            return tmpl.render(topic=topic, participants=participants_info)
        except Exception:  # noqa: BLE001
            parts = ", ".join(f"{p['name']}({p['role']})" for p in participants_info)
            return (
                f"You are hosting a meeting.\nTopic: {topic}\nParticipants: {parts}\n"
                "Let each participant speak in turn, then output minutes (decisions/action items/owners)."
            )
