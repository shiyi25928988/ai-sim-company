"""Company Skill Pool - company-level knowledge assets (see §八).

Stored in a Redis hash (aisim:skills). Agents inherit by level:
  COMPANY -> everyone; DEPARTMENT -> same department (scope contains the department name);
  ROLE -> same role (scope contains the role name); PERSONAL -> only the agent_id in scope.
`prompt_injection` is injected into the Agent's System Prompt by the LLMGateway.

Division of responsibility: Hermes (inside the Agent container) is responsible for "learning" (auto-extracting experience); this Pool is responsible for "managing"
(sharing/distribution/permissions/versioning). Currently there is no hermes in simulated mode, so the share_skill/learn_skill
tools + preset Skills drive Pool growth and inheritance.
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
    """Company-level Skill pool (Redis)."""

    def __init__(self, bus: MessageBus) -> None:
        self.bus = bus

    # ── CRUD + lifecycle ──
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

    async def delete(self, skill_id: str) -> bool:
        """Remove a Skill from the pool. Returns whether it existed."""
        existed = await self.get(skill_id) is not None
        await self.bus.hdel(channels.KEY_SKILLS, skill_id)
        return existed

    async def update(self, skill_id: str, fields: dict) -> Skill | None:
        """Update editable fields on a Skill (name/description/prompt_injection/category/level/scope)."""
        s = await self.get(skill_id)
        if s is None:
            return None
        if "name" in fields:
            s.name = fields["name"]
        if "description" in fields:
            s.description = fields["description"]
        if "prompt_injection" in fields:
            s.prompt_injection = fields["prompt_injection"]
        if "category" in fields:
            s.category = SkillCategory(fields["category"])
        if "level" in fields:
            s.level = SkillLevel(fields["level"])
        if "scope" in fields:
            s.scope = fields["scope"]
        s.version += 1
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
        """Keyword search (TODO: FTS5; MVP uses name/description substring)."""
        q = (query or "").lower()
        out = []
        for s in await self.list():
            if s.status != SkillStatus.PUBLISHED:
                continue
            if q in s.name.lower() or q in s.description.lower():
                out.append(s)
        return out

    # ── Inheritance ──
    async def get_effective_skills(
        self, agent_id: str, role: str, department: str
    ) -> list[Skill]:
        """The Skills currently in effect for an Agent (for System Prompt injection)."""
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
        """Seed preset Skills into the pool at startup (idempotent: skip if already exists)."""
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
    """New Agent onboarding: compute inherited Skills (see §八)."""
    skills = await pool.get_effective_skills(agent_id, role, department)
    logger.info("Agent %s 入职继承 %d 个 Skills", agent_id, len(skills))
    return skills
