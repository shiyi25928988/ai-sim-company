"""CompanyHub 主类 - 串联所有中枢组件 (见 §三)。

运行时:
- 连接 Redis，下发 CEO Profile 并登记运行态。
- 仿真时钟每 Tick: 广播 simulation:tick 给 Agent + 推送 state_snapshot 给前端。
- 监听 Agent 上报 (register/ready/offline/heartbeat/action/skill:new) 并维护状态。
- 对外提供 create_agent / remove_agent / snapshot 供 REST 接口调用。
"""

from __future__ import annotations

import asyncio
import logging
import re
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
    """Company App - 系统的中枢。前端 (Phaser) + 后端 (FastAPI) 一体。"""

    def __init__(self, config: Config) -> None:
        self.config = config

        # 通信 (先行，供其它组件注入)
        self.message_bus = MessageBus()
        self.meeting_system = MeetingSystem()

        # 仿真
        self.clock = SimulationClock(interval_ms=config.simulation.tick_interval_ms)
        self.economy = EconomyEngine(initial_capital=config.company.initial_capital)
        self.event_bus = EventBus()

        # Agent 管理
        self.agent_manager = AgentManager(self.message_bus)
        self.agent_runner = SimulatedAgentRunner(self)
        self.profile_registry = ProfileRegistry(self.message_bus)
        self.org_chart = OrgChart()

        # 任务
        self.task_manager = TaskManager(self.message_bus)

        # LLM
        self.llm_gateway = LLMGateway(config.llm)

        # 知识
        self.skill_pool = SkillPool(self.message_bus)
        self.llm_gateway.skill_pool = self.skill_pool

        # 持久化 (Hub 内存态: tick/经济/用量)
        self.db = Database()

        # 前端事件出口 (由 api 层注入 ws_manager.broadcast)
        self.on_frontend_event: Callable[[dict], Awaitable[None]] | None = None

        self._stale_task: asyncio.Task | None = None
        self._started = False

    # ═══ 生命周期 ═══
    async def start(self) -> None:
        if self._started:
            return
        logger.info("CompanyHub 启动中...")
        await self.message_bus.connect(self.config.redis_url)
        await self.agent_manager.connect(self.config)
        self.db.connect()
        self._restore_state()
        await self.skill_pool.seed_presets()

        await self._seed_ceo()
        await self._rehydrate_agents()

        self.clock.on_tick = self.on_tick
        await self.message_bus.listen_agents(self.handle_agent_event)

        if self.agent_manager.mode == "simulated":
            await self.agent_runner.start()

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
        await self.llm_gateway.aclose()
        await self.message_bus.close()
        self.db.close()
        self._started = False

    async def _seed_ceo(self) -> None:
        """公司创立: CEO 即存在 (本地 simulated 模式直接登记)。"""
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
        """从 Redis 重建 runner 的 Agent 注册表 (Hub 重启后恢复思考能力)。

        Redis 里的 Agent (AOF 持久化) 重启后仍在，但 runner 的内存注册表丢失；
        此处把所有 simulated Agent 重新注册到 runner，使其恢复思考。
        (Agent 记忆是内存态，不恢复；profile/role/skills 从 Redis 恢复。)
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
        """每 Tick: 广播时钟 -> 结算经济 -> 持久化 -> 推送前端快照 -> 驱动 Agent 思考。

        await_agents=False (播放模式): 并发 fire-and-forget (快)。
        await_agents=True (单步模式): 顺序+间隔 await (可观察节奏)。
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
            await self.agent_runner.on_tick(tick)  # simulated 模式下托管 Agent 主循环

    async def step(self) -> None:
        """单步: 推进一个 tick 并顺序执行 Agent (可观察)，供手动节奏控制。"""
        self.clock.tick += 1
        await self.on_tick(self.clock.tick, await_agents=True)

    def _restore_state(self) -> None:
        """从 SQLite 恢复 Hub 内存态 (tick/经济/用量)。"""
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

    # ═══ Agent 事件处理 (Agent -> Hub) ═══
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
        """Agent 容器报到 -> 下发其 Profile (docker 模式)。"""
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
        """Agent 动作汇报 -> 转发前端渲染事件。"""
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

    # ═══ 对外接口 (供 REST 调用) ═══
    async def create_agent(
        self,
        name: str,
        role: str,
        department: str = "General",
        salary: int = 0,
        personality: dict | Personality | None = None,
        report_to: str | None = None,
    ) -> dict:
        """创建一个新 Agent (CEO/HR 调用 create_agent 工具的落地)。"""
        agent_id = _make_agent_id(role, name)
        persona = personality_from_dict(personality)
        report_to = report_to or self.config.ceo.agent_id

        profile = self.profile_registry.generate_profile(
            agent_id, name, role, department, persona, salary, report_to
        )
        await self.profile_registry.save(profile)
        self.org_chart.add(agent_id, role, department, report_to)
        self.economy.add_salary(salary)

        if self.agent_manager.mode == "docker":
            # 容器启动后会自行报到 -> _on_agent_register 下发 Profile
            await self.agent_manager.create_container(agent_id, self.config.redis_url)
            await self.agent_manager.register(profile, AgentStatus.BOOTING, simulated=False)
        else:
            # simulated: 直接登记为 READY，并下发 Profile (供潜在的真实容器/调试订阅)
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

    # ═══ 任务 ═══
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
        """CEO/HR 创建任务并派发 (按角色或具体 Agent)。"""
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
        """Agent 完成任务 (认领 + 标记 done + 记录汇报)。"""
        task = await self.task_manager.complete(task_id, agent_id, result, self.clock.tick)
        if task is None:
            return None
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
        """Senior 把经验提炼成 ROLE 级 Skill 发布给某角色 (该角色全员继承)。"""
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:24] or "skill"
        skill = Skill(
            id=f"skill-{self.clock.tick}-{slug}",
            name=name,
            category=SkillCategory.TECHNICAL,
            level=SkillLevel.ROLE,
            scope=[target_role],
            description=f"由 {source_agent_id} 传授",
            prompt_injection=prompt_injection,
            created_by=source_agent_id,
            status=SkillStatus.PUBLISHED,
        )
        await self.skill_pool.create(skill)
        logger.info("[%s] 分享 Skill: %s -> %s", source_agent_id, name, target_role)
        return SkillPool.to_dict(skill)

    async def learn_skill(self, agent_id: str, query: str) -> dict:
        """Junior 从公司池搜索并学习一个 Skill (个人副本)。"""
        results = await self.skill_pool.search(query)
        if not results:
            return {"learned": None, "query": query}
        src = results[0]
        skill = Skill(
            id=f"skill-{self.clock.tick}-learn-{src.id}",
            name=src.name,
            category=src.category,
            level=SkillLevel.PERSONAL,
            scope=[agent_id],
            description=f"{agent_id} 从公司池学习",
            prompt_injection=src.prompt_injection,
            created_by=agent_id,
            created_from=src.id,
            status=SkillStatus.PUBLISHED,
        )
        await self.skill_pool.create(skill)
        logger.info("[%s] 学习 Skill: %s", agent_id, src.name)
        return SkillPool.to_dict(skill)

    # ═══ 会议 ═══
    async def call_meeting(self, caller_id: str, topic: str, participants: list[str]) -> str:
        """召集并 LLM 主持一场会议，返回纪要 (见 §六)。

        participants 为 agent_id 列表; 解析为名字后推 meeting_start (前端移人)，
        LLM 主持产出纪要，广播给参会者并推 meeting_minutes。
        """
        parts: list[dict] = []
        names: list[str] = []
        for pid in participants:
            st = await self.agent_manager.get(pid)
            if st:
                parts.append({"name": st["name"], "role": st["role"], "id": pid})
                names.append(st["name"])
        if not parts:
            return "无有效参会者"

        await self.emit_frontend({"type": "meeting_start", "participants": names})
        meeting = self.meeting_system.schedule(
            f"meeting-{self.clock.tick}-{caller_id}", topic, participants
        )
        host = await self.profile_registry.get(caller_id)
        if host is None:
            host = self.profile_registry.generate_ceo_profile(self.config)
        minutes = await self.meeting_system.run(meeting, parts, host, self.llm_gateway)
        # 纪要广播给全员
        await self.message_bus.broadcast_announcement(
            caller_id, f"[会议纪要:{topic}]\n{minutes}"
        )
        await self.emit_frontend(
            {"type": "meeting_minutes", "topic": topic, "minutes": minutes[:500],
             "by": caller_id, "participants": names}
        )
        logger.info("会议完成: %s (by %s)", topic, caller_id)
        return minutes

    async def snapshot(self) -> dict:
        """全量状态快照 (供 GET /api/state 与前端 state_snapshot)。"""
        agents = await self.agent_manager.list()
        # 附上每个 Agent 最近的思考/动作 (可观测性)
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

    # ═══ 前端事件 ═══
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
