"""Core data models - see architecture design doc §四 / §六 / §八.

These dataclasses / enums are the contract passed between Hub and Agent via Redis.
Field names match the doc and are serialized to JSON as dicts directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


# ═══════════════════════════════════════════════════════════
# Agent
# ═══════════════════════════════════════════════════════════


class AgentStatus(str, Enum):
    """Agent lifecycle states (see §四 state machine)."""

    BOOTING = "booting"
    INITIALIZING = "initializing"
    READY = "ready"
    WORKING = "working"
    OFFLINE = "offline"
    SHUTTING_DOWN = "shutting_down"


@dataclass
class Personality:
    """Big-5 personality traits, each dimension 0.0~1.0."""

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
    """Fault-tolerantly convert a dict to Personality.

    The LLM may use full names (openness) or Big-5 shorthand (O/C/E/A/N) as keys, and may include extra fields;
    here we map uniformly and ignore unknown keys.
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
    """The Agent's full identity - pushed by Company Hub (see §四).

    The Agent carries no LLM config; all LLM calls go through the Hub gateway.
    """

    agent_id: str  # "eng-jordan"
    name: str  # "Jordan"
    role: str  # "senior-engineer"
    department: str  # "Engineering"

    # Personality
    personality: Personality = field(default_factory=Personality)

    # Responsibilities
    responsibilities: list[str] = field(default_factory=list)
    report_to: str = ""  # Who they report to (agent_id)
    salary: int = 0

    # Capabilities
    system_prompt: str = ""  # Full System Prompt for the current Tick
    tools: list[str] = field(default_factory=list)  # Assigned by role
    skills: list[str] = field(default_factory=list)  # Inherited Skill ID list

    # State
    mood: float = 0.0  # -1.0 ~ 1.0
    energy: float = 100.0  # 0 ~ 100
    status: AgentStatus = AgentStatus.BOOTING

    # Resources
    workspace: str = ""  # /workspace/eng-jordan


# ═══════════════════════════════════════════════════════════
# Message
# ═══════════════════════════════════════════════════════════


class MessageType(str, Enum):
    """Four communication modes (see §六)."""

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
    """Unified format for inter-Agent communication (see §六)."""

    id: str
    type: MessageType
    sender: str  # agent_id
    recipients: list[str]  # Target agent_id list
    content: str
    content_type: ContentType = ContentType.TEXT
    channel: str | None = None  # Channel name (when type=channel)
    reply_to: str | None = None  # ID of the message being replied to
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
    """Skill inheritance levels (see §八)."""

    COMPANY = "company"  # Inherited by everyone
    DEPARTMENT = "department"  # Inherited by department
    ROLE = "role"  # Inherited by same role
    PERSONAL = "personal"  # Only self


class SkillStatus(str, Enum):
    """Skill lifecycle states (see §八)."""

    DRAFT = "draft"
    PUBLISHED = "published"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


@dataclass
class Skill:
    """Company-level Skill (see §八).

    `prompt_injection` is the core content injected into the Agent's System Prompt.
    """

    id: str
    name: str  # "Production deployment checklist"
    category: SkillCategory
    level: SkillLevel
    scope: list[str] = field(default_factory=list)  # Who can use it: ["senior-engineer", ...]
    description: str = ""
    prompt_injection: str = ""  # ★ Injected into the System Prompt
    created_by: str = ""  # Which Agent created it
    created_from: str | None = None  # Learned from which task
    usage_count: int = 0
    rating: float = 0.0
    status: SkillStatus = SkillStatus.DRAFT
    version: int = 1
    history: list[dict] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════
# Task
# ═══════════════════════════════════════════════════════════


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    BLOCKED = "blocked"


@dataclass
class Task:
    """A work task (created by CEO/HR, assigned to a role or a specific Agent)."""

    id: str
    title: str
    description: str = ""
    status: TaskStatus = TaskStatus.PENDING
    assignee: str = ""  # agent_id (empty = claim by role)
    assignee_role: str = ""  # Role (dispatched to any Agent of this role)
    project: str = ""
    priority: str = "normal"  # low | normal | high
    created_by: str = ""
    created_tick: int = 0
    completed_tick: int = 0
    completed_by: str = ""
    result: str = ""  # Report on completion
