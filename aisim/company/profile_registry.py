"""Agent identity Profile generation and management (see §四).

A new Agent's system_prompt / tools / skills are assembled here before being pushed.
Profiles are persisted to a Redis hash (aisim:profiles) and pushed via agent:{id}:profile.
"""

from __future__ import annotations

import logging

from aisim.comm.message_bus import MessageBus
from aisim.shared import channels
from aisim.shared.config import CEOConfig, Config
from aisim.shared.models import AgentProfile, Personality

logger = logging.getLogger(__name__)

# Role -> available tools (see §四 role/tool mapping table)
TOOLS_BY_ROLE: dict[str, list[str]] = {
    "ceo": [
        "create_agent", "send_message", "call_meeting", "web_search",
        "create_task", "view_finance", "set_strategy", "approve_budget", "create_skill",
    ],
    "hr-director": [
        "create_agent", "send_message", "call_meeting", "view_team",
        "schedule_interview", "onboard_agent", "share_skill", "create_task",
    ],
    "product-manager": [
        "send_message", "web_search", "create_task", "find_skill", "call_meeting",
    ],
    "senior-engineer": [
        "complete_task", "send_message", "share_skill", "code_review", "web_search",
        "write_file", "read_file", "list_files", "find_skill", "create_skill", "run_claude_code",
    ],
    "junior-engineer": [
        "complete_task", "send_message", "ask_for_help", "learn_skill",
        "write_file", "read_file", "list_files", "find_skill", "run_claude_code",
    ],
    "designer": [
        "complete_task", "send_message", "web_search",
        "write_file", "read_file", "list_files", "find_skill", "create_skill", "run_claude_code",
    ],
    "product-manager": [
        "complete_task", "send_message", "call_meeting", "web_search", "create_task",
        "write_file", "read_file", "list_files", "find_skill", "create_skill", "share_skill",
    ],
    "marketer": [
        "complete_task", "send_message", "call_meeting", "web_search",
        "write_file", "read_file", "list_files", "find_skill", "create_skill",
    ],
    "data-analyst": [
        "complete_task", "send_message", "web_search",
        "write_file", "read_file", "list_files", "find_skill", "create_skill", "run_claude_code",
    ],
    "qa-engineer": [
        "complete_task", "send_message", "web_search",
        "write_file", "read_file", "list_files", "find_skill", "learn_skill", "create_skill",
        "share_skill", "run_claude_code",
    ],
}

# Tools for custom/unknown roles (no entry in TOOLS_BY_ROLE) so custom agents can act.
DEFAULT_TOOLS: list[str] = [
    "complete_task", "send_message", "web_search",
    "write_file", "read_file", "list_files", "find_skill", "create_skill",
]


def _profile_to_dict(profile: AgentProfile) -> dict:
    """AgentProfile -> a JSON-serializable dict (including nested enums/dataclasses)."""
    p = profile.__dict__.copy()
    p["personality"] = profile.personality.__dict__
    p["status"] = profile.status.value
    return p


class ProfileRegistry:
    """Agent Profile storage and generation (Redis)."""

    def __init__(self, bus: MessageBus) -> None:
        self.bus = bus
        self._cache: dict[str, AgentProfile] = {}

    # ── Generation ──
    def generate_ceo_profile(self, config: Config) -> AgentProfile:
        """Generate the CEO's Profile at company founding."""
        ceo: CEOConfig = config.ceo
        return AgentProfile(
            agent_id=ceo.agent_id,
            name=ceo.name,
            role=ceo.role,
            department=ceo.department,
            personality=Personality(),
            responsibilities=["公司战略", "招聘决策", "预算审批"],
            report_to="",
            salary=ceo.salary,
            system_prompt="",  # assembled dynamically by LLMGateway._build_system_prompt
            tools=TOOLS_BY_ROLE.get("ceo", []),
            skills=[],
            workspace=f"/workspace/{ceo.agent_id}",
        )

    def generate_profile(
        self,
        agent_id: str,
        name: str,
        role: str,
        department: str,
        personality: Personality,
        salary: int,
        report_to: str,
        description: str = "",
    ) -> AgentProfile:
        """When HR/CEO call create_agent, generate the target Agent's Profile.

        `description` (markdown) overrides the role template as the Agent's system
        prompt base - used for custom roles (no prompt template / tool mapping).
        """
        system_prompt = ""
        if description and description.strip():
            system_prompt = f"You are {name}, a {role} at the company.\n\n{description.strip()}"
        profile = AgentProfile(
            agent_id=agent_id,
            name=name,
            role=role,
            department=department,
            personality=personality,
            responsibilities=_responsibilities_for(role),
            report_to=report_to,
            salary=salary,
            system_prompt=system_prompt,
            tools=TOOLS_BY_ROLE.get(role) or DEFAULT_TOOLS,
            skills=[],
            workspace=f"/workspace/{agent_id}",
        )
        self._cache[agent_id] = profile
        return profile

    # ── Redis storage ──
    async def save(self, profile: AgentProfile) -> None:
        self._cache[profile.agent_id] = profile
        await self.bus.hset_json(channels.KEY_PROFILES, profile.agent_id, _profile_to_dict(profile))

    async def get(self, agent_id: str) -> AgentProfile | None:
        if agent_id in self._cache:
            return self._cache[agent_id]
        data = await self.bus.hget_json(channels.KEY_PROFILES, agent_id)
        return self._from_dict(data) if data else None

    async def list_all(self) -> list[AgentProfile]:
        data = await self.bus.hgetall_json(channels.KEY_PROFILES)
        return [self._from_dict(v) for v in data.values()]

    async def remove(self, agent_id: str) -> None:
        self._cache.pop(agent_id, None)
        await self.bus.hdel(channels.KEY_PROFILES, agent_id)

    async def publish(self, profile: AgentProfile) -> None:
        """Push the Profile to agent:{id}:profile via Redis."""
        await self.save(profile)
        await self.bus.publish(channels.agent_profile(profile.agent_id), _profile_to_dict(profile))
        logger.info("下发 Profile: %s (%s)", profile.agent_id, profile.role)

    @staticmethod
    def _from_dict(data: dict) -> AgentProfile:
        p = Personality(**(data.get("personality") or {}))
        return AgentProfile(
            agent_id=data["agent_id"],
            name=data["name"],
            role=data["role"],
            department=data["department"],
            personality=p,
            responsibilities=data.get("responsibilities", []),
            report_to=data.get("report_to", ""),
            salary=int(data.get("salary", 0)),
            system_prompt=data.get("system_prompt", ""),
            tools=data.get("tools", []),
            skills=data.get("skills", []),
            mood=float(data.get("mood", 0.0)),
            energy=float(data.get("energy", 100.0)),
            status=data.get("status", "booting"),
            workspace=data.get("workspace", ""),
        )


def _responsibilities_for(role: str) -> list[str]:
    return {
        "hr-director": ["招聘落地", "候选人画像", "入职与 Skill 继承"],
        "senior-engineer": ["生产级编码", "技术方案", "代码审查", "经验传授"],
        "junior-engineer": ["编码与测试", "求助与学习"],
        "designer": ["设计方案", "视觉资产", "品牌一致性"],
        "product-manager": ["产品规划", "需求文档", "优先级排序", "跨团队协调"],
        "marketer": ["市场推广", "内容创作", "品牌定位", "用户调研"],
        "data-analyst": ["数据分析", "指标监控", "实验设计", "报表输出"],
        "qa-engineer": ["测试用例", "质量把关", "缺陷追踪", "测试自动化"],
    }.get(role, [])
