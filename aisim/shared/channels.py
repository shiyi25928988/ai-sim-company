"""Redis Pub/Sub 通道命名约定 - 见架构设计文档 §六。

固定通道用大写常量; 带 agent_id 的通道用小写函数，避免拼接错误。
"""

from __future__ import annotations

# ── Hub -> All Agents / 前端 ──
SIMULATION_TICK = "simulation:tick"  # 仿真时钟信号 (每 Tick 广播)
FRONTEND_EVENTS = "frontend:events"  # Hub -> 前端 WS 渲染事件

# ── Agent -> Hub ──
AGENT_REGISTER = "agent:register"  # 报到
AGENT_READY = "agent:ready"  # 就绪
AGENT_OFFLINE = "agent:offline"  # 离线
HUB_ACTION = "hub:action"  # 动作汇报
HUB_SKILL_NEW = "hub:skill:new"  # 新 Skill 上报


def agent_inbox(agent_id: str) -> str:
    """Hub -> Agent: 专属收件箱。"""
    return f"agent:{agent_id}:inbox"


def agent_profile(agent_id: str) -> str:
    """Hub -> Agent: 身份 Profile 下发。"""
    return f"agent:{agent_id}:profile"


def agent_heartbeat(agent_id: str) -> str:
    """Agent -> Hub: 心跳 (5s/次)。"""
    return f"agent:{agent_id}:heartbeat"


def agent_skills_init(agent_id: str) -> str:
    """Hub -> Agent: 入职时 Skill 初始化。"""
    return f"agent:{agent_id}:skills:init"


def agent_skills_pending(agent_id: str) -> str:
    """Hub -> Agent: 待学习的 Skill。"""
    return f"agent:{agent_id}:skills:pending"


# ═══════════════════════════════════════════════════════════
# 状态存储键 (Redis 持久化，非 Pub/Sub 通道)
# ═══════════════════════════════════════════════════════════
KEY_PROFILES = "aisim:profiles"  # hash: agent_id -> AgentProfile JSON
KEY_AGENTS = "aisim:agents"  # hash: agent_id -> Agent 运行态 JSON
KEY_TASKS = "aisim:tasks"  # hash: task_id -> Task JSON
KEY_SKILLS = "aisim:skills"  # hash: skill_id -> Skill JSON
KEY_META = "aisim:meta"  # string: 全局元信息 (tick 等) JSON
