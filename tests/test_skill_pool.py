"""SkillPool unit tests - uses FakeBus (no Redis)."""

from __future__ import annotations

import pytest

from aisim.skills.pool import SkillPool
from aisim.shared.models import Skill, SkillCategory, SkillLevel, SkillStatus

pytestmark = pytest.mark.asyncio


class FakeBus:
    def __init__(self) -> None:
        self.data: dict[str, dict] = {}

    async def hset_json(self, name, key, value):
        self.data.setdefault(name, {})[key] = value

    async def hget_json(self, name, key):
        return self.data.get(name, {}).get(key)

    async def hgetall_json(self, name):
        return dict(self.data.get(name, {}))

    async def hdel(self, name, *keys):
        for k in keys:
            self.data.get(name, {}).pop(k, None)


async def test_seed_presets_idempotent():
    pool = SkillPool(FakeBus())  # type: ignore[arg-type]
    n1 = await pool.seed_presets()
    n2 = await pool.seed_presets()
    assert n1 > 0 and n2 == 0  # second run skips all


async def test_effective_skills_role_inheritance():
    pool = SkillPool(FakeBus())  # type: ignore[arg-type]
    await pool.seed_presets()
    # senior-engineer inherits: Python dev (scope includes senior) + code review spec (senior only)
    sr = await pool.get_effective_skills("eng-jordan", "senior-engineer", "Engineering")
    sr_names = {s.name for s in sr}
    assert "Python 开发" in sr_names
    assert "代码审查规范" in sr_names
    # junior-engineer: inherits Python dev + Git basics, but not code review spec
    jr = await pool.get_effective_skills("eng-sam", "junior-engineer", "Engineering")
    jr_names = {s.name for s in jr}
    assert "Python 开发" in jr_names
    assert "Git 基础" in jr_names
    assert "代码审查规范" not in jr_names


async def test_personal_skill_only_owner():
    pool = SkillPool(FakeBus())  # type: ignore[arg-type]
    await pool.create(Skill(
        id="s-pers", name="我的笔记", category=SkillCategory.TECHNICAL,
        level=SkillLevel.PERSONAL, scope=["eng-jordan"], prompt_injection="私货",
        status=SkillStatus.PUBLISHED,
    ))
    mine = await pool.get_effective_skills("eng-jordan", "senior-engineer", "Engineering")
    others = await pool.get_effective_skills("eng-sam", "senior-engineer", "Engineering")
    assert any(s.name == "我的笔记" for s in mine)
    assert all(s.name != "我的笔记" for s in others)


async def test_search():
    pool = SkillPool(FakeBus())  # type: ignore[arg-type]
    await pool.seed_presets()
    res = await pool.search("python")
    assert any("Python" in s.name for s in res)
    assert all(s.status == SkillStatus.PUBLISHED for s in res)
