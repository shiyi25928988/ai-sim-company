"""Agent runtime state management (simulated mode).

Agents run in-process; their state is persisted to SQLite via MessageBus.
No Docker containers.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from aisim.comm.message_bus import MessageBus
from aisim.shared import channels
from aisim.shared.config import Config
from aisim.shared.models import AgentProfile, AgentStatus

logger = logging.getLogger(__name__)

HEARTBEAT_TIMEOUT_S = 15.0


@dataclass
class AgentHandle:
    agent_id: str
    status: str = "unknown"
    simulated: bool = False


class AgentManager:
    """Agent lifecycle management + runtime state storage (in-memory + SQLite)."""

    def __init__(self, bus: MessageBus) -> None:
        self.bus = bus
        self.mode: str = "simulated"
        self._handles: dict[str, AgentHandle] = {}

    async def connect(self, config: Config) -> None:
        self.mode = "simulated"
        logger.info("AgentManager: simulated 模式")

    # ── Runtime state storage ──
    async def register(self, profile: AgentProfile, status: AgentStatus, simulated: bool) -> None:
        state = self._state_from(profile, status, simulated)
        self._handles[profile.agent_id] = AgentHandle(
            agent_id=profile.agent_id, status=status.value, simulated=simulated
        )
        await self.bus.hset_json(channels.KEY_AGENTS, profile.agent_id, state)

    async def set_status(self, agent_id: str, status: AgentStatus) -> None:
        state = await self.bus.hget_json(channels.KEY_AGENTS, agent_id)
        if state is None:
            logger.warning("set_status: 未知 agent %s", agent_id)
            return
        state["status"] = status.value
        await self.bus.hset_json(channels.KEY_AGENTS, agent_id, state)
        if agent_id in self._handles:
            self._handles[agent_id].status = status.value

    async def update_heartbeat(self, agent_id: str) -> None:
        state = await self.bus.hget_json(channels.KEY_AGENTS, agent_id)
        if state is None:
            return
        state["last_heartbeat"] = time.time()
        await self.bus.hset_json(channels.KEY_AGENTS, agent_id, state)

    async def get(self, agent_id: str) -> dict | None:
        return await self.bus.hget_json(channels.KEY_AGENTS, agent_id)

    async def list(self) -> list[dict]:
        data = await self.bus.hgetall_json(channels.KEY_AGENTS)
        return list(data.values())

    async def remove_state(self, agent_id: str) -> None:
        self._handles.pop(agent_id, None)
        await self.bus.hdel(channels.KEY_AGENTS, agent_id)

    async def remove(self, agent_id: str) -> None:
        """Remove agent state."""
        await self.remove_state(agent_id)

    # ── Heartbeat timeout check ──
    async def mark_stale_offline(self) -> list[str]:
        """Return the list of agent_ids judged OFFLINE (skips simulated ones)."""
        agents = await self.list()
        now = time.time()
        stale: list[str] = []
        for state in agents:
            if state.get("simulated"):
                continue
            last = state.get("last_heartbeat", 0)
            if last and now - last > HEARTBEAT_TIMEOUT_S and state.get("status") != "offline":
                await self.set_status(state["agent_id"], AgentStatus.OFFLINE)
                stale.append(state["agent_id"])
        return stale

    # ── Utilities ──
    @staticmethod
    def _state_from(profile: AgentProfile, status: AgentStatus, simulated: bool) -> dict:
        return {
            "agent_id": profile.agent_id,
            "name": profile.name,
            "role": profile.role,
            "department": profile.department,
            "status": status.value,
            "salary": profile.salary,
            "mood": profile.mood,
            "energy": profile.energy,
            "simulated": simulated,
            "last_heartbeat": 0.0,
            "x": 0,
            "y": 0,
        }
