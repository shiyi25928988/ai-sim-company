"""Agent container orchestration - create/stop/delete Agent containers via the Docker API (see §四/§五).

Two backends:
- docker:    real docker run (aiodocker); env is only REDIS_URL+AGENT_ID; mounts private + shared workspace.
             The Agent container reports in over Redis on its own after starting -> the Hub pushes its Profile.
- simulated: default for local dev. Does not start a container; registers runtime state directly in Redis,
             so the Hub interface and frontend can be fully exercised without hermes/Docker.

Agent runtime state is persisted to a Redis hash (aisim:agents).
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass

from aisim.comm.message_bus import MessageBus
from aisim.shared import channels
from aisim.shared.config import Config
from aisim.shared.models import AgentProfile, AgentStatus

logger = logging.getLogger(__name__)

AGENT_IMAGE = "ai-sim-company-agent:latest"
NETWORK = "ai-sim-company_aisim-net"
HEARTBEAT_TIMEOUT_S = 15.0  # heartbeat timeout -> marked OFFLINE


@dataclass
class AgentHandle:
    agent_id: str
    container_id: str | None = None
    status: str = "unknown"
    simulated: bool = False


class AgentManager:
    """Agent lifecycle management + runtime state storage (Redis)."""

    def __init__(self, bus: MessageBus) -> None:
        self.bus = bus
        self.mode: str = "simulated"
        self._docker = None
        self._handles: dict[str, AgentHandle] = {}

    async def connect(self, config: Config) -> None:
        self.mode = config.agent_backend
        if self.mode == "docker":
            try:
                import aiodocker  # noqa: F401 lazy import
                import os

                docker_host = os.environ.get("DOCKER_HOST", "unix:///var/run/docker.sock")
                self._docker = aiodocker.Docker(url=docker_host)
                await self._docker.version()
                logger.info("AgentManager: docker 模式已就绪 (%s)", docker_host)
            except Exception:  # noqa: BLE001
                logger.warning("aiodocker 不可用，回退到 simulated 模式: %s", config.agent_backend)
                self.mode = "simulated"
        logger.info("AgentManager: %s 模式", self.mode)

    # ── Runtime state storage (Redis) ──
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

    # ── Create / destroy containers ──
    async def create_container(
        self, agent_id: str, redis_url: str, memory: str = "256m", cpus: float = 0.5
    ) -> AgentHandle:
        """docker mode: docker run a new Agent container."""
        mem_bytes = _parse_memory(memory)
        config = {
            "Image": AGENT_IMAGE,
            "Env": [f"REDIS_URL={redis_url}", f"AGENT_ID={agent_id}"],
            "HostConfig": {
                "NetworkMode": NETWORK,
                "Memory": mem_bytes,
                "NanoCpus": int(cpus * 1e9),
                "RestartPolicy": {"Name": "unless-stopped"},
                "Binds": [
                    f"ai-sim-company_agent_{agent_id}:/workspace/{agent_id}",
                    "ai-sim-company_company_files:/workspace/shared",
                ],
            },
        }
        container = await self._docker.containers.create_or_replace(
            name=f"aisim-agent-{agent_id}", config=config
        )
        await container.start()
        handle = AgentHandle(agent_id=agent_id, container_id=container.id, status="booting")
        self._handles[agent_id] = handle
        logger.info("Agent 容器已启动: %s (container=%s)", agent_id, container.id)
        return handle

    async def remove_container(self, agent_id: str) -> None:
        """docker mode: stop and remove the container."""
        handle = self._handles.get(agent_id)
        if handle and handle.container_id and self._docker is not None:
            try:
                c = self._docker.containers.container(handle.container_id)
                await c.stop()
                await c.delete()
                logger.info("Agent 容器已销毁: %s", agent_id)
            except Exception:  # noqa: BLE001
                logger.exception("销毁容器失败: %s", agent_id)

    async def remove(self, agent_id: str) -> None:
        """Unified teardown (stop container in docker mode + delete Redis state)."""
        await self.remove_container(agent_id)
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


def _parse_memory(spec: str) -> int:
    """'256m' / '1g' -> bytes."""
    spec = spec.strip().lower()
    try:
        if spec.endswith("g"):
            return int(float(spec[:-1]) * 1024 ** 3)
        if spec.endswith("m"):
            return int(float(spec[:-1]) * 1024 ** 2)
        return int(spec)
    except ValueError:
        return 256 * 1024 ** 2
