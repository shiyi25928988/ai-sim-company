"""Redis Pub/Sub channel naming conventions - see architecture design doc §六.

Fixed channels use uppercase constants; channels with an agent_id use lowercase functions to avoid concatenation errors.
"""

from __future__ import annotations

# ── Hub -> All Agents / frontend ──
SIMULATION_TICK = "simulation:tick"  # Simulation clock signal (broadcast every Tick)
FRONTEND_EVENTS = "frontend:events"  # Hub -> frontend WS render events

# ── Agent -> Hub ──
AGENT_REGISTER = "agent:register"  # Report in
AGENT_READY = "agent:ready"  # Ready
AGENT_OFFLINE = "agent:offline"  # Offline
HUB_ACTION = "hub:action"  # Action report
HUB_SKILL_NEW = "hub:skill:new"  # New Skill report


def agent_inbox(agent_id: str) -> str:
    """Hub -> Agent: dedicated inbox."""
    return f"agent:{agent_id}:inbox"


def agent_profile(agent_id: str) -> str:
    """Hub -> Agent: identity Profile push."""
    return f"agent:{agent_id}:profile"


def agent_heartbeat(agent_id: str) -> str:
    """Agent -> Hub: heartbeat (every 5s)."""
    return f"agent:{agent_id}:heartbeat"


def agent_skills_init(agent_id: str) -> str:
    """Hub -> Agent: Skill initialization on onboarding."""
    return f"agent:{agent_id}:skills:init"


def agent_skills_pending(agent_id: str) -> str:
    """Hub -> Agent: Skills pending learning."""
    return f"agent:{agent_id}:skills:pending"


# ═══════════════════════════════════════════════════════════
# State storage keys (Redis persistence, not Pub/Sub channels)
# ═══════════════════════════════════════════════════════════
KEY_PROFILES = "aisim:profiles"  # hash: agent_id -> AgentProfile JSON
KEY_AGENTS = "aisim:agents"  # hash: agent_id -> Agent runtime state JSON
KEY_TASKS = "aisim:tasks"  # hash: task_id -> Task JSON
KEY_SKILLS = "aisim:skills"  # hash: skill_id -> Skill JSON
KEY_META = "aisim:meta"  # string: global metadata (tick, etc.) JSON
