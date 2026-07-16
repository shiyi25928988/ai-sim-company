"""Agent ↔ Hub Skill sync (see §八 sync mechanism).

- Agent completes a complex task -> generates a new Skill locally -> reports via hub:skill:new -> enters the company pool (draft)
- CTO/Lead reviews -> published -> agent:{id}:skills:pending notification
- Agent provides usage feedback -> updates rating
"""

from __future__ import annotations

import logging

from aisim.shared import channels
from aisim.skills.pool import SkillPool

logger = logging.getLogger(__name__)


class SkillSync:
    """Handles bidirectional Skill sync between Agent and Company Pool."""

    def __init__(self, pool: SkillPool) -> None:
        self.pool = pool

    async def on_skill_new(self, redis, agent_id: str, skill_data: dict) -> None:
        """Agent reports a new Skill -> enters the pool (draft)."""
        # TODO: construct a Skill object and pool.create(...)
        logger.info("Agent %s 上报新 Skill: %s", agent_id, skill_data.get("name"))

    async def notify_pending(self, redis, agent_id: str, skill_id: str) -> None:
        """Notify the Agent of a Skill pending learning/update."""
        await redis.publish(
            channels.agent_skills_pending(agent_id),
            {"skill_id": skill_id},
        )

    async def on_usage_feedback(self, skill_id: str, rating: float) -> None:
        """Agent usage feedback -> update rating."""
        skill = self.pool.get(skill_id)
        if skill is None:
            return
        # TODO: update rating via sliding average
        skill.usage_count += 1
        logger.info("Skill %s 反馈评分 %.2f (累计使用 %d)", skill_id, rating, skill.usage_count)
