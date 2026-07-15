"""核心数据模型 - 见架构设计文档 §四 / §六 / §八。

这些 dataclass / enum 是 Hub 与 Agent 之间通过 Redis 传递的契约，
字段命名与文档保持一致，序列化为 JSON 时直接作为 dict 传输。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


# ═══════════════════════════════════════════════════════════
# Agent
# ═══════════════════════════════════════════════════════════


class AgentStatus(str, Enum):
    """Agent 生命周期状态 (见 §四 状态机)。"""

    BOOTING = "booting"
    INITIALIZING = "initializing"
    READY = "ready"
    WORKING = "working"
    OFFLINE = "offline"
    SHUTTING_DOWN = "shutting_down"


@dataclass
class Personality:
    """Big-5 人格特质，各维度 0.0~1.0。"""

    openness: float = 0.5
    conscientiousness: float = 0.5
    extraversion: float = 0.5
    agreeableness: float = 0.5
    neuroticism: float = 0.5


_PERSONALITY_KEY_MAP = {
    "openness": "openness", "o": "openness",
    "conscientiousness": "conscientiousness", "c": "conscientiousness",
    "extraversion": "extraversion", "e": "extraversion",
    "agreeableness": "agreeableness", "a": "agreeableness",
    "neuroticism": "neuroticism", "n": "neuroticism",
}


def personality_from_dict(personality: "Personality | dict | None") -> "Personality":
    """容错地把 dict 转 Personality。

    LLM 可能用全名 (openness) 或 Big-5 简写 (O/C/E/A/N) 作 key，且可能带多余字段；
    这里统一映射并忽略未知 key。
    """
    if isinstance(personality, Personality):
        return personality
    if isinstance(personality, dict):
        mapped: dict[str, float] = {}
        for k, v in personality.items():
            field = _PERSONALITY_KEY_MAP.get(str(k).lower())
            if not field:
                continue
            try:
                mapped[field] = float(v)
            except (TypeError, ValueError):
                pass
        return Personality(**mapped)
    return Personality()


@dataclass
class AgentProfile:
    """Agent 的完整身份 - 由 Company Hub 下发 (见 §四)。

    Agent 不携带 LLM 配置; LLM 调用全部走 Hub 网关。
    """

    agent_id: str  # "eng-jordan"
    name: str  # "Jordan"
    role: str  # "senior-engineer"
    department: str  # "Engineering"

    # 人格
    personality: Personality = field(default_factory=Personality)

    # 职责
    responsibilities: list[str] = field(default_factory=list)
    report_to: str = ""  # 汇报给谁 (agent_id)
    salary: int = 0

    # 能力
    system_prompt: str = ""  # 当前 Tick 的完整 System Prompt
    tools: list[str] = field(default_factory=list)  # 根据角色分配
    skills: list[str] = field(default_factory=list)  # 继承的 Skill ID 列表

    # 状态
    mood: float = 0.0  # -1.0 ~ 1.0
    energy: float = 100.0  # 0 ~ 100
    status: AgentStatus = AgentStatus.BOOTING

    # 资源
    workspace: str = ""  # /workspace/eng-jordan


# ═══════════════════════════════════════════════════════════
# 消息
# ═══════════════════════════════════════════════════════════


class MessageType(str, Enum):
    """四种通信模式 (见 §六)。"""

    DM = "dm"  # 1:1
    CHANNEL = "channel"  # 1:N
    MEETING = "meeting"  # N:N
    ANNOUNCEMENT = "announcement"  # 1:All


class ContentType(str, Enum):
    TEXT = "text"
    CODE = "code"
    DECISION = "decision"
    TASK = "task"
    FEEDBACK = "feedback"


class Priority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


@dataclass
class Message:
    """Agent 间通信的统一格式 (见 §六)。"""

    id: str
    type: MessageType
    sender: str  # agent_id
    recipients: list[str]  # 目标 agent_id 列表
    content: str
    content_type: ContentType = ContentType.TEXT
    channel: str | None = None  # 频道名 (type=channel 时)
    reply_to: str | None = None  # 回复的消息 ID
    priority: Priority = Priority.NORMAL
    timestamp: float = 0.0


# ═══════════════════════════════════════════════════════════
# Skill
# ═══════════════════════════════════════════════════════════


class SkillCategory(str, Enum):
    TECHNICAL = "technical"
    MANAGEMENT = "management"
    CREATIVE = "creative"
    OPERATIONS = "operations"


class SkillLevel(str, Enum):
    """Skill 继承层级 (见 §八)。"""

    COMPANY = "company"  # 全员继承
    DEPARTMENT = "department"  # 部门继承
    ROLE = "role"  # 同角色继承
    PERSONAL = "personal"  # 仅自己


class SkillStatus(str, Enum):
    """Skill 生命周期状态 (见 §八)。"""

    DRAFT = "draft"
    PUBLISHED = "published"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


@dataclass
class Skill:
    """公司级 Skill (见 §八)。

    `prompt_injection` 是注入到 Agent System Prompt 的核心内容。
    """

    id: str
    name: str  # "生产环境部署 Checklist"
    category: SkillCategory
    level: SkillLevel
    scope: list[str] = field(default_factory=list)  # 谁能用: ["senior-engineer", ...]
    description: str = ""
    prompt_injection: str = ""  # ★ 注入到 System Prompt
    created_by: str = ""  # 哪个 Agent 创建的
    created_from: str | None = None  # 从哪个任务中学到的
    usage_count: int = 0
    rating: float = 0.0
    status: SkillStatus = SkillStatus.DRAFT
    version: int = 1
    history: list[dict] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════
# 任务
# ═══════════════════════════════════════════════════════════


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    BLOCKED = "blocked"


@dataclass
class Task:
    """一个工作任务 (CEO/HR 创建，分配给某角色或具体 Agent)。"""

    id: str
    title: str
    description: str = ""
    status: TaskStatus = TaskStatus.PENDING
    assignee: str = ""  # agent_id (空=按角色认领)
    assignee_role: str = ""  # 角色 (派给该角色的任一 Agent)
    project: str = ""
    priority: str = "normal"  # low | normal | high
    created_by: str = ""
    created_tick: int = 0
    completed_tick: int = 0
    completed_by: str = ""
    result: str = ""  # 完成时的汇报
