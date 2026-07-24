"""CompanyHub main class - wires together all core components (see §三).

Runtime:
- Connect to Redis, push the CEO Profile and register its runtime state.
- Each simulation clock Tick: broadcast simulation:tick to Agents + push state_snapshot to the frontend.
- Listen for Agent reports (register/ready/offline/heartbeat/action/skill:new) and maintain state.
- Expose create_agent / remove_agent / snapshot for the REST layer to call.
"""

from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path
from typing import Any, Awaitable, Callable

from aisim.comm.meeting import MeetingSystem
from aisim.comm.message_bus import MessageBus
from aisim.company.agent_manager import AgentManager
from aisim.company.agent_runner import SimulatedAgentRunner
from aisim.company.org_chart import OrgChart
from aisim.company.profile_registry import ProfileRegistry
from aisim.company.task_manager import TaskManager
from aisim.db import Database
from aisim.llm.gateway import LLMGateway
from aisim.llm.mcp import MCPClientManager
from aisim.shared import channels
from aisim.shared.config import Config
from aisim.shared.models import (
    AgentStatus,
    Personality,
    Skill,
    SkillCategory,
    SkillLevel,
    SkillStatus,
    personality_from_dict,
)
from aisim.simulation.clock import SimulationClock
from aisim.simulation.economy import EconomyEngine
from aisim.simulation.event_bus import EventBus
from aisim.skills.pool import SkillPool

logger = logging.getLogger(__name__)


class CompanyHub:
    """Company App - the core of the system. Frontend (Phaser) + backend (FastAPI) in one."""

    def __init__(self, config: Config) -> None:
        self.config = config

        # Communication (initialized first, injected into other components)
        self.message_bus = MessageBus()
        self.meeting_system = MeetingSystem()

        # Simulation
        self.clock = SimulationClock(interval_ms=config.simulation.tick_interval_ms)
        self.economy = EconomyEngine(initial_capital=config.company.initial_capital)
        self.event_bus = EventBus()

        # Agent management
        self.agent_manager = AgentManager(self.message_bus)
        self.agent_runner = SimulatedAgentRunner(self)
        self.profile_registry = ProfileRegistry(self.message_bus)
        self.org_chart = OrgChart()

        # Tasks
        self.task_manager = TaskManager(self.message_bus)

        # LLM
        self.llm_gateway = LLMGateway(config.llm)

        # MCP (agent connection to external MCP servers)
        self.mcp_manager = MCPClientManager()

        # User/board directives injected into the CEO's next tick (console intervention)
        self.directives: list[str] = []

        # Knowledge
        self.skill_pool = SkillPool(self.message_bus)
        self.llm_gateway.skill_pool = self.skill_pool

        # Persistence (Hub in-memory state: tick/economy/usage)
        self.db = Database()

        # Frontend event outlet (api layer injects ws_manager.broadcast)
        self.on_frontend_event: Callable[[dict], Awaitable[None]] | None = None

        self._stale_task: asyncio.Task | None = None
        self._started = False

    # ═══ Lifecycle ═══
    async def start(self) -> None:
        if self._started:
            return
        logger.info("CompanyHub 启动中...")
        self.db.connect()
        await self.message_bus.connect()
        self.message_bus.attach_db(self.db)
        await self.agent_manager.connect(self.config)
        self._restore_state()
        await self.skill_pool.seed_presets()
        await self.seed_skill_packs()

        await self._seed_ceo()
        await self._rehydrate_agents()

        self.clock.on_tick = self.on_tick
        await self.message_bus.listen_agents(self.handle_agent_event)

        if self.agent_manager.mode == "simulated":
            await self.agent_runner.start()

        # MCP servers
        self.mcp_manager.configure(self.config.llm.mcp_servers)
        await self.mcp_manager.connect_all()

        if self.config.simulation.auto_start:
            await self.clock.start()
        else:
            logger.info("仿真默认暂停 (SIM_AUTO_START=false)；POST /api/simulation/control play 或前端 ▶ 启动")

        self._stale_task = asyncio.create_task(self._stale_loop())
        self._started = True
        logger.info("CompanyHub 就绪。CEO=%s backend=%s", self.config.ceo.agent_id, self.agent_manager.mode)

    async def stop(self) -> None:
        if not self._started:
            return
        await self.clock.stop()
        await self.agent_runner.stop()
        if self._stale_task is not None:
            self._stale_task.cancel()
            self._stale_task = None
        await self.mcp_manager.disconnect_all()
        await self.llm_gateway.aclose()
        await self.message_bus.close()
        self.db.close()
        self._started = False

    async def apply_config(self, new_config: Config) -> dict:
        """Apply a new config at runtime: stop, clear all state, reinit components, restart.

        Used by POST /api/config so the user can reconfigure business/budget without restarting
        the process. The Hub instance is reused so existing references (e.g. routes' `hub`) stay
        valid. Returns the fresh snapshot.
        """
        if self._started:
            await self.stop()
        self.config = new_config

        # Clear persisted + hot state for a fresh start
        try:
            await self.message_bus.connect(self.config.redis_url)
            await self.message_bus.delete(
                channels.KEY_AGENTS, channels.KEY_PROFILES, channels.KEY_TASKS,
                channels.KEY_SKILLS, channels.KEY_META,
            )
            await self.message_bus.close()
        except Exception:  # noqa: BLE001
            logger.exception("clear Redis failed during apply_config")
        try:
            db = Database()
            db.connect()
            db.delete("hub_state")
            db.close()
        except Exception:  # noqa: BLE001
            logger.exception("clear SQLite failed during apply_config")

        # Reinit components (keep message_bus / on_frontend_event)
        self.clock = SimulationClock(interval_ms=new_config.simulation.tick_interval_ms)
        self.economy = EconomyEngine(initial_capital=new_config.company.initial_capital)
        self.agent_manager = AgentManager(self.message_bus)
        self.agent_runner = SimulatedAgentRunner(self)
        self.profile_registry = ProfileRegistry(self.message_bus)
        self.org_chart = OrgChart()
        self.task_manager = TaskManager(self.message_bus)
        self.skill_pool = SkillPool(self.message_bus)
        self.llm_gateway = LLMGateway(new_config.llm)
        self.llm_gateway.skill_pool = self.skill_pool
        self.db = Database()
        self._started = False

        await self.start()
        return await self.snapshot()

    async def seed_skill_packs(self) -> None:
        """Load default skill packs from aisim/skills/packs/ (each subdir with SKILL.md).

        Each pack's SKILL.md frontmatter (name/description) becomes the skill metadata;
        the body is copied to the workspace as the full guide (agent reads via read_file).
        prompt_injection is a short description + pointer (avoids bloating system prompts).
        """
        import re

        import yaml

        packs_dir = Path(__file__).parent.parent / "skills" / "packs"
        if not packs_dir.exists():
            return
        ws_base = Path(self.config.company.workspace_dir) / "skills"
        count = 0
        for skill_dir in sorted(packs_dir.iterdir()):
            if not skill_dir.is_dir():
                continue
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue
            text = skill_md.read_text(encoding="utf-8")
            meta: dict = {}
            m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", text, re.DOTALL)
            if m:
                meta = yaml.safe_load(m.group(1)) or {}
            name = str(meta.get("name", skill_dir.name))
            description = str(meta.get("description", "") or "")
            slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:24] or name
            short_desc = description[:200] + ("..." if len(description) > 200 else "")
            prompt_inj = (
                short_desc
                + f"\n\nFull guide: read_file skills/{slug}/SKILL.md for detailed instructions."
            ).strip()
            skill = Skill(
                id=f"pack-{slug}",
                name=name,
                category=SkillCategory.TECHNICAL,
                level=SkillLevel.COMPANY,
                scope=[],
                description=short_desc,
                prompt_injection=prompt_inj,
                created_by="system",
                status=SkillStatus.PUBLISHED,
            )
            await self.skill_pool.create(skill)
            target_dir = (ws_base / slug).resolve()
            target_dir.mkdir(parents=True, exist_ok=True)
            for f in skill_dir.iterdir():
                if f.is_file() and f.suffix in (".md", ".py"):
                    (target_dir / f.name).write_bytes(f.read_bytes())
            count += 1
        if count:
            logger.info("Seeded %d skill packs from %s", count, packs_dir)

    async def _seed_ceo(self) -> None:
        """Company founding: the CEO exists immediately (registered directly in local simulated mode)."""
        ceo_id = self.config.ceo.agent_id
        if await self.agent_manager.get(ceo_id) is not None:
            logger.info("CEO 已存在，跳过 seed: %s", ceo_id)
            return
        profile = self.profile_registry.generate_ceo_profile(self.config)
        await self.profile_registry.save(profile)
        await self.agent_manager.register(profile, AgentStatus.READY, simulated=True)
        self.org_chart.add(profile.agent_id, profile.role, profile.department)
        if self.agent_manager.mode == "simulated":
            self.agent_runner.register(profile)
        logger.info("CEO 已就位: %s (%s)", profile.name, profile.agent_id)

    async def _rehydrate_agents(self) -> None:
        """Rebuild the runner's Agent registry from Redis (restore thinking ability after Hub restart).

        Agents in Redis (AOF-persisted) survive a restart, but the runner's in-memory registry is lost;
        here we re-register all simulated Agents into the runner so they resume thinking.
        (Agent memory is in-memory and is not restored; profile/role/skills are restored from Redis.)
        """
        if self.agent_manager.mode != "simulated":
            return
        agents = await self.agent_manager.list()
        n = 0
        for a in agents:
            agent_id = a.get("agent_id")
            if not agent_id or self.agent_runner.has(agent_id):
                continue
            profile = await self.profile_registry.get(agent_id)
            if profile is not None:
                self.agent_runner.register(profile)
                n += 1
        if n:
            logger.info("从 Redis 恢复 %d 个 Agent 到 runner 注册表", n)

    # ═══ Tick ═══
    async def on_tick(self, tick: int, await_agents: bool = False) -> None:
        """Each Tick: broadcast clock -> settle economy -> persist -> push frontend snapshot -> drive Agent thinking.

        await_agents=False (play mode): concurrent fire-and-forget (fast).
        await_agents=True (step mode): sequential + interval await (observable pace).
        """
        await self.message_bus.broadcast_tick(tick)
        self.economy.apply_tick(tick)
        self.db.save_json("hub_state", {
            "tick": tick,
            "economy": self.economy.snapshot(),
            "usage": self.llm_gateway.usage_today,
        })
        await self.emit_frontend(await self.snapshot_event())
        if await_agents:
            await self.agent_runner.run_tick_sequential(tick)
        else:
            await self.agent_runner.on_tick(tick)  # host the Agent main loop in simulated mode

    async def step(self) -> None:
        """Single step: advance one tick and run Agents sequentially (observable), for manual pace control."""
        self.clock.tick += 1
        await self.on_tick(self.clock.tick, await_agents=True)

    def _restore_state(self) -> None:
        """Restore Hub in-memory state from SQLite (tick/economy/usage)."""
        saved = self.db.load_json("hub_state")
        if not saved:
            return
        self.clock.tick = int(saved.get("tick", 0))
        eco = saved.get("economy", {}) or {}
        self.economy.state.capital = int(eco.get("capital", self.economy.state.capital))
        self.economy.state.monthly_burn = int(eco.get("monthly_burn", self.economy.state.monthly_burn))
        self.llm_gateway.usage_today = int(saved.get("usage", 0))
        logger.info(
            "恢复状态: tick=%d capital=%d usage=%d",
            self.clock.tick, self.economy.state.capital, self.llm_gateway.usage_today,
        )

    async def _stale_loop(self) -> None:
        while self._started:
            try:
                stale = await self.agent_manager.mark_stale_offline()
                for agent_id in stale:
                    logger.warning("Agent 心跳超时，判定离线: %s", agent_id)
            except asyncio.CancelledError:  # noqa: PERF203
                raise
            except Exception:  # noqa: BLE001
                logger.exception("stale 检查异常")
            await asyncio.sleep(5)

    # ═══ Agent event handling (Agent -> Hub) ═══
    async def handle_agent_event(self, event: dict) -> None:
        ch = event.get("_channel")
        if ch == channels.AGENT_REGISTER:
            await self._on_agent_register(event)
        elif ch == channels.AGENT_READY:
            agent_id = event.get("agent_id") or event.get("data")
            if agent_id:
                await self.agent_manager.set_status(agent_id, AgentStatus.READY)
                await self._emit_agent_created(agent_id)
        elif ch == channels.AGENT_OFFLINE:
            agent_id = event.get("agent_id") or event.get("data")
            if agent_id:
                await self.agent_manager.set_status(agent_id, AgentStatus.OFFLINE)
        elif ch == channels.HUB_ACTION:
            await self._on_hub_action(event)
        elif ch == channels.HUB_SKILL_NEW:
            logger.info("Agent 上报新 Skill: %s", event)
        else:
            logger.debug("未处理事件: %s", ch)

    async def _on_agent_register(self, event: dict) -> None:
        """Agent container reports in -> push its Profile (docker mode)."""
        agent_id = event.get("agent_id")
        if not agent_id:
            return
        profile = await self.profile_registry.get(agent_id)
        if profile is None:
            logger.warning("报到的 Agent 无 Profile (未预先创建?): %s", agent_id)
            return
        await self.profile_registry.publish(profile)
        await self.agent_manager.set_status(agent_id, AgentStatus.INITIALIZING)

    async def _on_hub_action(self, event: dict) -> None:
        """Agent action report -> forward as a frontend render event."""
        sender = event.get("sender") or event.get("agent_id") or "unknown"
        content = event.get("content", "")
        await self.emit_frontend(
            {
                "type": "agent_action",
                "agent": sender,
                "action": content,
                "target": event.get("target"),
            }
        )

    # ═══ External interface (for REST to call) ═══
    async def create_agent(
        self,
        name: str,
        role: str,
        department: str = "General",
        salary: int = 0,
        personality: dict | Personality | None = None,
        report_to: str | None = None,
        description: str = "",
    ) -> dict:
        """Create a new Agent (the landing of the create_agent tool called by CEO/HR)."""
        agent_id = _make_agent_id(role, name)
        persona = personality_from_dict(personality)
        report_to = report_to or self.config.ceo.agent_id

        profile = self.profile_registry.generate_profile(
            agent_id, name, role, department, persona, salary, report_to, description=description
        )
        await self.profile_registry.save(profile)
        self.org_chart.add(agent_id, role, department, report_to)
        self.economy.add_salary(salary)

        if self.agent_manager.mode == "docker":
            # Container reports in on its own after starting -> _on_agent_register pushes the Profile
            await self.agent_manager.create_container(agent_id, self.config.redis_url)
            await self.agent_manager.register(profile, AgentStatus.BOOTING, simulated=False)
        else:
            # simulated: register directly as READY and push the Profile (for potential real containers / debug subscriptions)
            await self.agent_manager.register(profile, AgentStatus.READY, simulated=True)
            await self.profile_registry.publish(profile)
            self.agent_runner.register(profile)

        await self._emit_agent_created(agent_id)
        logger.info("创建 Agent: %s (%s) salary=%s backend=%s", name, role, salary, self.agent_manager.mode)
        return await self.agent_manager.get(agent_id) or {"agent_id": agent_id, "name": name, "role": role}

    async def remove_agent(self, agent_id: str) -> None:
        self.agent_runner.unregister(agent_id)
        profile = await self.profile_registry.get(agent_id)
        await self.agent_manager.remove(agent_id)
        if profile is not None:
            self.economy.remove_salary(profile.salary)
        self.org_chart.remove(agent_id)
        await self.profile_registry.remove(agent_id)
        logger.info("移除 Agent: %s", agent_id)

    # ═══ Tasks ═══
    async def create_task(
        self,
        title: str,
        description: str = "",
        assignee_role: str = "",
        assignee: str = "",
        project: str = "",
        priority: str = "normal",
        created_by: str = "",
    ) -> dict:
        """PM/CEO create a task. Dedup: skip if a similar pending task exists or too many pending."""
        existing = await self.task_manager.list()
        pending = [t for t in existing if t.status != "done"]
        if len(pending) >= 8:
            logger.info("create_task 跳过: 已有 %d 个未完成任务 (上限 8)", len(pending))
            return {"skipped": "too many pending tasks", "pending": len(pending)}
        title_lower = title.lower().strip()
        for t in pending:
            existing_lower = t.title.lower().strip()
            if title_lower == existing_lower or title_lower in existing_lower or existing_lower in title_lower:
                logger.info("create_task 跳过: 与现有任务重叠 '%s'", t.title)
                return {"skipped": "duplicate", "existing": t.title}
        task = await self.task_manager.create(
            title=title,
            description=description,
            assignee_role=assignee_role,
            assignee=assignee,
            project=project,
            priority=priority,
            created_by=created_by,
            tick=self.clock.tick,
        )
        await self.emit_frontend(
            {
                "type": "task_created",
                "task_id": task.id,
                "title": task.title,
                "assignee_role": task.assignee_role,
                "assignee": task.assignee,
            }
        )
        logger.info("创建任务: %s -> %s", title, assignee_role or assignee)
        return TaskManager.to_dict(task)

    async def complete_task(self, task_id: str, agent_id: str, result: str) -> dict | None:
        """Agent completes a task (claim + mark done + record the report)."""
        task = await self.task_manager.complete(task_id, agent_id, result, self.clock.tick)
        if task is None:
            return None
        await self.agent_manager.set_status(agent_id, AgentStatus.READY)
        await self.emit_frontend(
            {
                "type": "task_completed",
                "task_id": task.id,
                "title": task.title,
                "result": (result or "")[:200],
                "by": agent_id,
            }
        )
        return TaskManager.to_dict(task)

    # ═══ Skill ═══
    async def share_skill(
        self, source_agent_id: str, name: str, prompt_injection: str, target_role: str
    ) -> dict:
        """A senior distills experience into a ROLE-level Skill and publishes it to a role (inherited by all members of that role)."""
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:24] or "skill"
        skill = Skill(
            id=f"skill-{self.clock.tick}-{slug}",
            name=name,
            category=SkillCategory.TECHNICAL,
            level=SkillLevel.ROLE,
            scope=[target_role],
            description=f"Taught by {source_agent_id}",
            prompt_injection=prompt_injection,
            created_by=source_agent_id,
            status=SkillStatus.PUBLISHED,
        )
        await self.skill_pool.create(skill)
        logger.info("[%s] 分享 Skill: %s -> %s", source_agent_id, name, target_role)
        return SkillPool.to_dict(skill)

    async def learn_skill(self, agent_id: str, query: str) -> dict:
        """A junior searches the company pool and learns a Skill (personal copy)."""
        results = await self.skill_pool.search(query)
        if not results:
            return {"learned": None, "query": query}
        src = results[0]
        slug = re.sub(r"[^a-z0-9]+", "-", src.name.lower()).strip("-")[:24] or "skill"
        skill = Skill(
            id=f"skill-{self.clock.tick}-{agent_id}-learn-{slug}",
            name=src.name,
            category=src.category,
            level=SkillLevel.PERSONAL,
            scope=[agent_id],
            description=f"{agent_id} learned from company pool",
            prompt_injection=src.prompt_injection,
            created_by=agent_id,
            created_from=src.id,
            status=SkillStatus.PUBLISHED,
        )
        await self.skill_pool.create(skill)
        logger.info("[%s] 学习 Skill: %s", agent_id, src.name)
        return SkillPool.to_dict(skill)

    async def create_skill(
        self, name: str, description: str, prompt_injection: str,
        category: str, level: str, scope: list[str], created_by: str = "user",
    ) -> dict:
        """User-uploaded Skill (from the /skills page). Published immediately so agents can inherit it."""
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:24] or "skill"
        skill = Skill(
            id=f"skill-{self.clock.tick}-{slug}",
            name=name,
            category=SkillCategory(category),
            level=SkillLevel(level),
            scope=scope,
            description=description,
            prompt_injection=prompt_injection,
            created_by=created_by,
            status=SkillStatus.PUBLISHED,
        )
        await self.skill_pool.create(skill)
        logger.info("[user] created Skill: %s (level=%s)", name, level)
        return SkillPool.to_dict(skill)

    async def delete_skill(self, skill_id: str) -> dict:
        """Remove a user-uploaded Skill."""
        existed = await self.skill_pool.delete(skill_id)
        logger.info("[user] deleted Skill: %s (existed=%s)", skill_id, existed)
        return {"removed": skill_id, "existed": existed}

    async def update_skill(self, skill_id: str, **fields) -> dict | None:
        """Update editable fields on a Skill. Returns the updated dict, or None if not found."""
        s = await self.skill_pool.update(skill_id, fields)
        if s is None:
            return None
        logger.info("[user] updated Skill: %s", skill_id)
        return SkillPool.to_dict(s)

    async def find_skill(self, query: str) -> list[dict]:
        """Search published skills by keyword; return summaries (no copy created)."""
        results = await self.skill_pool.search(query)
        return [
            {"name": s.name, "level": s.level.value, "scope": s.scope,
             "description": s.description, "prompt_injection": s.prompt_injection[:200]}
            for s in results
        ]

    # ═══ Workspace files ═══
    def _ws_root(self, scope: str, agent_id: str | None = None) -> Path:
        base = Path(self.config.company.workspace_dir)
        if scope == "personal":
            sub = agent_id or "personal"
        else:
            sub = "shared"
        return (base / sub).resolve()

    async def list_workspace(self, path: str, scope: str, agent_id: str | None = None) -> list[dict]:
        root = self._ws_root(scope, agent_id)
        full = (root / path.lstrip("/")).resolve()
        if not str(full).startswith(str(root)) or not full.exists():
            return []
        return [{"name": p.name, "is_dir": p.is_dir()} for p in sorted(full.iterdir())]

    async def read_workspace(self, path: str, scope: str, agent_id: str | None = None) -> str | None:
        root = self._ws_root(scope, agent_id)
        full = (root / path.lstrip("/")).resolve()
        if not str(full).startswith(str(root)) or not full.exists() or full.is_dir():
            return None
        return full.read_text(encoding="utf-8", errors="replace")

    # ═══ Meeting ═══
    async def call_meeting(self, caller_id: str, topic: str, participants: list[str]) -> str:
        """Convene and have an LLM host a meeting, return the minutes (see §六).

        participants is a list of agent_ids; resolved to names then meeting_start is pushed (frontend moves people),
        the LLM hosts and produces minutes, which are broadcast to participants and pushed as meeting_minutes.
        """
        parts: list[dict] = []
        names: list[str] = []
        for pid in participants:
            st = await self.agent_manager.get(pid)
            if st and st.get("status") != "working":
                parts.append({"name": st["name"], "role": st["role"], "id": pid})
                names.append(st["name"])
        if not parts:
            return "No valid participants"

        await self.emit_frontend({"type": "meeting_start", "participants": names})
        meeting = self.meeting_system.schedule(
            f"meeting-{self.clock.tick}-{caller_id}", topic, participants
        )
        host = await self.profile_registry.get(caller_id)
        if host is None:
            host = self.profile_registry.generate_ceo_profile(self.config)
        minutes = await self.meeting_system.run(meeting, parts, host, self.llm_gateway)
        # Broadcast minutes to everyone
        await self.message_bus.broadcast_announcement(
            caller_id, f"[Meeting minutes: {topic}]\n{minutes}"
        )
        await self.emit_frontend(
            {"type": "meeting_minutes", "topic": topic, "minutes": minutes[:500],
             "by": caller_id, "participants": names}
        )
        logger.info("会议完成: %s (by %s)", topic, caller_id)
        return minutes

    async def snapshot(self) -> dict:
        """Full state snapshot (for GET /api/state and the frontend state_snapshot)."""
        agents = await self.agent_manager.list()
        # Attach each Agent's recent thoughts/actions (observability)
        for a in agents:
            a["recent"] = self.agent_runner.recent_memory(a.get("agent_id", ""), 5)
        return {
            "company": self.config.company.name,
            "tick": self.clock.tick,
            "running": self.clock.running,
            "economy": self.economy.snapshot(),
            "agents": agents,
            "tasks": await self.task_manager.list_dicts(),
            "skills": await self.skill_pool.list_dicts(),
        }

    async def snapshot_event(self) -> dict:
        snap = await self.snapshot()
        return {
            "type": "state_snapshot",
            "tick": snap["tick"],
            "company": snap["company"],
            "agents": snap["agents"],
            "tasks": snap["tasks"],
            "skills": snap["skills"],
            "bank": snap["economy"]["capital"],
            "economy": snap["economy"],
        }

    # ═══ Frontend events ═══
    async def emit_frontend(self, event: dict) -> None:
        if self.on_frontend_event is not None:
            try:
                await self.on_frontend_event(event)
            except Exception:  # noqa: BLE001
                logger.exception("前端事件推送失败")

    async def _emit_agent_created(self, agent_id: str) -> None:
        state = await self.agent_manager.get(agent_id)
        if not state:
            return
        await self.emit_frontend(
            {"type": "agent_created", "agent_id": agent_id, "name": state["name"], "role": state["role"]}
        )


def _make_agent_id(role: str, name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    prefix = role.split("-")[0] if role else "agent"
    return f"{prefix}-{slug}" or f"agent-{slug}"
