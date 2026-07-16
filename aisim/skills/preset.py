"""Preset Skills - base skills bundled with a role at CREATE time (see §八 Skill sources)."""

from __future__ import annotations

from aisim.shared.models import Skill, SkillCategory, SkillLevel, SkillStatus

# Base Skills bundled with a role (level=PERSONAL, cloned as a personal Skill when a new Agent is created)
PRESET_SKILLS: dict[str, list[Skill]] = {
    "senior-engineer": [
        Skill(
            id="preset-python-dev",
            name="Python 开发",
            category=SkillCategory.TECHNICAL,
            level=SkillLevel.ROLE,
            scope=["senior-engineer", "junior-engineer"],
            description="Python 工程开发基础",
            prompt_injection="遵循 PEP8; 优先用类型注解; 写单元测试。",
            status=SkillStatus.PUBLISHED,
        ),
        Skill(
            id="preset-code-review",
            name="代码审查规范",
            category=SkillCategory.TECHNICAL,
            level=SkillLevel.ROLE,
            scope=["senior-engineer"],
            description="Code Review 标准流程",
            prompt_injection="审查时关注: 正确性 / 边界 / 可读性 / 测试覆盖。",
            status=SkillStatus.PUBLISHED,
        ),
    ],
    "junior-engineer": [
        Skill(
            id="preset-git-basics",
            name="Git 基础",
            category=SkillCategory.TECHNICAL,
            level=SkillLevel.ROLE,
            scope=["junior-engineer"],
            description="Git 版本控制基础",
            prompt_injection="小步提交; 清晰的 commit message; 不直接推 main。",
            status=SkillStatus.PUBLISHED,
        ),
    ],
    "designer": [
        Skill(
            id="preset-design-system",
            name="设计系统基础",
            category=SkillCategory.CREATIVE,
            level=SkillLevel.ROLE,
            scope=["designer"],
            description="品牌一致性规范",
            prompt_injection="遵循品牌色板与组件库; 导出 SVG 资产。",
            status=SkillStatus.PUBLISHED,
        ),
    ],
    "hr-director": [
        Skill(
            id="preset-hiring-playbook",
            name="招聘手册",
            category=SkillCategory.OPERATIONS,
            level=SkillLevel.ROLE,
            scope=["hr-director"],
            description="标准招聘流程",
            prompt_injection="按需设岗 -> 画像 -> 创建 Agent -> 入职继承 Skills。",
            status=SkillStatus.PUBLISHED,
        ),
    ],
}
