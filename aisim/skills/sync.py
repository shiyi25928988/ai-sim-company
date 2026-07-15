"""Agent ↔ Hub Skill 同步 (见 §八 同步机制)。

- Agent 完成复杂任务 -> 本地生成新 Skill -> hub:skill:new 上报 -> 入公司池 (draft)
- CTO/Lead 审核 -> published -> agent:{id}:skills:pending 通知
- Agent 使用反馈 -> 更新评分
"""

from __future__ import annotations

import logging

from aisim.shared import channels
from aisim.skills.pool import SkillPool

logger = logging.getLogger(__name__)


class SkillSync:
    """处理 Skill 在 Agent 与 Company Pool 之间的双向同步。"""

    def __init__(self, pool: SkillPool) -> None:
        self.pool = pool

    async def on_skill_new(self, redis, agent_id: str, skill_data: dict) -> None:
        """Agent 上报新 Skill -> 入池 (draft)。"""
        # TODO: 构造 Skill 对象并 pool.create(...)
        logger.info("Agent %s 上报新 Skill: %s", agent_id, skill_data.get("name"))

    async def notify_pending(self, redis, agent_id: str, skill_id: str) -> None:
        """通知 Agent 有待学习/更新的 Skill。"""
        await redis.publish(
            channels.agent_skills_pending(agent_id),
            {"skill_id": skill_id},
        )

    async def on_usage_feedback(self, skill_id: str, rating: float) -> None:
        """Agent 使用反馈 -> 更新评分。"""
        skill = self.pool.get(skill_id)
        if skill is None:
            return
        # TODO: 滑动平均更新 rating
        skill.usage_count += 1
        logger.info("Skill %s 反馈评分 %.2f (累计使用 %d)", skill_id, rating, skill.usage_count)
