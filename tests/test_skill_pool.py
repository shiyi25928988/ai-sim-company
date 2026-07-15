"""SkillPool 单元测试 - 用 FakeBus (无 Redis)。"""

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
    assert n1 > 0 and n2 == 0  # 第二次全跳过


async def test_effective_skills_role_inheritance():
    pool = SkillPool(FakeBus())  # type: ignore[arg-type]
    await pool.seed_presets()
    # senior-engineer 继承: Python 开发 (scope 含 senior) + 代码审查规范 (仅 senior)
    sr = await pool.get_effective_skills("eng-jordan", "senior-engineer", "Engineering")
    sr_names = {s.name for s in sr}
    assert "Python 开发" in sr_names
    assert "代码审查规范" in sr_names
    # junior-engineer: 继承 Python 开发 + Git 基础，但不继承 代码审查规范
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
