"""Identity prompt generation helpers (see §七 _build_system_prompt).

The Agent's System Prompt is dynamically assembled by the Hub before each LLM call:
base identity + company context + Skills injection. Templates are in aisim/llm/prompts/*.j2.
"""

from __future__ import annotations

from aisim.shared.models import AgentProfile


def build_identity_block(profile: AgentProfile) -> str:
    """Build the base identity description block."""
    return (
        f"你是 {profile.name}，担任 {profile.role}，隶属 {profile.department} 部门。\n"
        f"你的 agent_id 是 {profile.agent_id}，向 {profile.report_to or '董事会'} 汇报。\n"
        f"职责: {', '.join(profile.responsibilities) or '(待定义)'}。\n"
    )


def build_company_context(profile: AgentProfile) -> str:
    """Build the company context block (TODO: inject funds/team/current strategy)."""
    return "公司上下文: (由 Hub 在运行时填充: 资金、团队、战略、近期事件)"


def build_skills_block(skill_injections: list[str]) -> str:
    """Merge the prompt_injection of inherited Skills into an injection block."""
    if not skill_injections:
        return ""
    return "\n\n".join(f"## Skill\n{s}" for s in skill_injections)
