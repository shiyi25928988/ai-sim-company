"""身份 Prompt 生成辅助 (见 §七 _build_system_prompt)。

Agent 的 System Prompt 在每次调 LLM 前由 Hub 动态组装:
基础身份 + 公司上下文 + Skills 注入。模板见 aisim/llm/prompts/*.j2。
"""

from __future__ import annotations

from aisim.shared.models import AgentProfile


def build_identity_block(profile: AgentProfile) -> str:
    """生成基础身份描述块。"""
    return (
        f"你是 {profile.name}，担任 {profile.role}，隶属 {profile.department} 部门。\n"
        f"你的 agent_id 是 {profile.agent_id}，向 {profile.report_to or '董事会'} 汇报。\n"
        f"职责: {', '.join(profile.responsibilities) or '(待定义)'}。\n"
    )


def build_company_context(profile: AgentProfile) -> str:
    """生成公司上下文块 (TODO: 注入资金/团队/当前战略)。"""
    return "公司上下文: (由 Hub 在运行时填充: 资金、团队、战略、近期事件)"


def build_skills_block(skill_injections: list[str]) -> str:
    """把已继承的 Skills 的 prompt_injection 合并成注入块。"""
    if not skill_injections:
        return ""
    return "\n\n".join(f"## Skill\n{s}" for s in skill_injections)
