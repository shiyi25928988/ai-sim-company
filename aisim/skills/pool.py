"""Company Skill Pool - 公司级知识资产 (见 §八)。

Redis hash (aisim:skills) 存储。Agent 按 level 继承:
  COMPANY -> 全员; DEPARTMENT -> 同部门 (scope 含部门名);
  ROLE -> 同角色 (scope 含角色名); PERSONAL -> 仅 scope 中的 agent_id。
`prompt_injection` 由 LLMGateway 注入到 Agent 的 System Prompt。

职责分工: Hermes (Agent 容器内) 负责"学"(自动提取经验)；本 Pool 负责"管"
(共享/分发/权限/版本)。当前 simulated 模式无 hermes，故用 share_skill/learn_skill
工具 + 预设 Skills 来驱动 Pool 增长与继承。
"""

from __future__ import annotations

import logging

from aisim.comm.message_bus import MessageBus
from aisim.shared import channels
from aisim.shared.models import Skill, SkillCategory, SkillLevel, SkillStatus

logger = logging.getLogger(__name__)


def _to_dict(skill: Skill) -> dict:
    d = skill.__dict__.copy()
    d["category"] = skill.category.value
    d["level"] = skill.level.value
    d["status"] = skill.status.value
    return d


def _from_dict(data: dict) -> Skill:
    return Skill(
        id=data["id"],
        name=data.get("name", ""),
        category=SkillCategory(data.get("category", "technical")),
        level=SkillLevel(data.get("level", "company")),
        scope=data.get("scope", []),
        description=data.get("description", ""),
        prompt_injection=data.get("prompt_injection", ""),
        created_by=data.get("created_by", ""),
        created_from=data.get("created_from"),
        usage_count=int(data.get("usage_count", 0)),
        rating=float(data.get("rating", 0.0)),
        status=SkillStatus(data.get("status", "draft")),
        version=int(data.get("version", 1)),
        history=data.get("history", []),
    )


class SkillPool:
    """公司级 Skill 池 (Redis)。"""

    def __init__(self, bus: MessageBus) -> None:
        self.bus = bus

    # ── CRUD + 生命周期 ──
    async def create(self, skill: Skill) -> Skill:
        await self._save(skill)
        logger.info("新 Skill: %s (level=%s) by %s", skill.name, skill.level.value, skill.created_by)
        return skill

    async def _save(self, skill: Skill) -> None:
        await self.bus.hset_json(channels.KEY_SKILLS, skill.id, _to_dict(skill))

    async def publish(self, skill_id: str) -> Skill | None:
        s = await self.get(skill_id)
        if s is not None:
            s.status = SkillStatus.PUBLISHED
            await self._save(s)
        return s

    async def get(self, skill_id: str) -> Skill | None:
        data = await self.bus.hget_json(channels.KEY_SKILLS, skill_id)
        return _from_dict(data) if data else None

    async def list(self) -> list[Skill]:
        data = await self.bus.hgetall_json(channels.KEY_SKILLS)
        return [_from_dict(v) for v in data.values()]

    async def list_dicts(self) -> list[dict]:
        return [_to_dict(s) for s in await self.list()]

    async def search(self, query: str) -> list[Skill]:
        """关键词检索 (TODO: FTS5；MVP 用 name/description 子串)。"""
        q = (query or "").lower()
        out = []
        for s in await self.list():
            if s.status != SkillStatus.PUBLISHED:
                continue
            if q in s.name.lower() or q in s.description.lower():
                out.append(s)
        return out

    # ── 继承 ──
    async def get_effective_skills(
        self, agent_id: str, role: str, department: str
    ) -> list[Skill]:
        """某 Agent 当前生效的 Skills (供 System Prompt 注入)。"""
        out = []
        for s in await self.list():
            if s.status != SkillStatus.PUBLISHED:
                continue
            if s.level == SkillLevel.COMPANY:
                out.append(s)
            elif s.level == SkillLevel.DEPARTMENT and department in s.scope:
                out.append(s)
            elif s.level == SkillLevel.ROLE and role in s.scope:
                out.append(s)
            elif s.level == SkillLevel.PERSONAL and agent_id in s.scope:
                out.append(s)
        return out

    async def seed_presets(self) -> int:
        """启动时把预设 Skills 灌入池 (幂等: 已存在则跳过)。"""
        from aisim.skills.preset import PRESET_SKILLS

        count = 0
        for skills in PRESET_SKILLS.values():
            for s in skills:
                if await self.get(s.id) is None:
                    await self._save(s)
                    count += 1
        if count:
            logger.info(" seeded %d 个预设 Skill", count)
        return count

    @staticmethod
    def to_dict(skill: Skill) -> dict:
        return _to_dict(skill)


async def onboard_agent(
    pool: SkillPool, agent_id: str, role: str, department: str
) -> list[Skill]:
    """新 Agent 入职: 计算继承的 Skills (见 §八)。"""
    skills = await pool.get_effective_skills(agent_id, role, department)
    logger.info("Agent %s 入职继承 %d 个 Skills", agent_id, len(skills))
    return skills
