"""SimulatedAgentRunner - simulated 模式下在 Hub 内托管 Agent 主循环。

设计折中: simulated 模式没有真实 Agent 容器 (hermes 不可用)，因此由 Hub 进程
为每个 simulated Agent 跑一个 tick 循环，直接 in-process 调用 LLMGateway.chat
(等价于"走 Hub LLM Gateway")。docker 模式下 Agent 在各自容器内运行，不经过本运行器。

多轮工具循环 (ReAct / OpenAI tools loop):
  每 Tick:
    snapshot -> 组装 prompt -> [LLM.chat -> 若有 tool_calls 则执行并把结果回填 -> 再 chat]
    重复直到无 tool_calls 或达到 max_iters。工具结果会回传给 LLM，故 web_search/
    write_file 等可被"搜完/写完再看结果"地使用 (尽管多数工具仍是桩)。
busy 标志避免同一 Agent 的 tick 重叠 (LLM 调用慢于 tick 间隔时跳过)。
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field

from aisim.agent.memory import MemoryEntry, MemoryManager
from aisim.shared.models import AgentProfile

logger = logging.getLogger(__name__)


@dataclass
class _AgentRuntime:
    profile: AgentProfile
    memory: MemoryManager = field(default_factory=lambda: MemoryManager(""))
    busy: bool = False


class SimulatedAgentRunner:
    """Hub 内托管的 simulated Agent 主循环。"""

    def __init__(self, hub) -> None:
        self.hub = hub
        self._agents: dict[str, _AgentRuntime] = {}
        self._running = False
        self._tasks: set[asyncio.Task] = set()

    async def start(self) -> None:
        self._running = True
        logger.info("SimulatedAgentRunner 启动 (agents=%d)", len(self._agents))

    async def stop(self) -> None:
        self._running = False
        for t in list(self._tasks):
            t.cancel()
        self._tasks.clear()

    # ── 注册 ──
    def register(self, profile: AgentProfile) -> None:
        self._agents[profile.agent_id] = _AgentRuntime(
            profile=profile, memory=MemoryManager(profile.agent_id)
        )

    def unregister(self, agent_id: str) -> None:
        self._agents.pop(agent_id, None)

    def has(self, agent_id: str) -> bool:
        return agent_id in self._agents

    def recent_memory(self, agent_id: str, limit: int = 5) -> list[dict]:
        """某 Agent 最近的思考/动作 (供前端 AgentPanel 展示)。"""
        rt = self._agents.get(agent_id)
        if not rt:
            return []
        return [{"content": m.content, "type": m.memory_type} for m in rt.memory.recent(limit)]

    # ── Tick ──
    async def on_tick(self, tick: int) -> None:
        """每个仿真 Tick (播放模式): 并发派发非忙 Agent 思考 (fire-and-forget，快)。"""
        if not self._running:
            return
        # Agent 每 N 个 tick 思考一次 (1=每次; 控成本)。hub 仍会推 snapshot/经济。
        think_every = getattr(getattr(self.hub.config, "simulation", None), "agent_think_every", 1) or 1
        if think_every > 1 and tick % think_every != 0:
            return
        snapshot = await self.hub.snapshot()
        for agent_id, rt in list(self._agents.items()):
            if rt.busy:
                continue
            task = asyncio.create_task(self._safe_tick(agent_id, snapshot))
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)

    async def run_tick_sequential(self, tick: int) -> None:
        """单步模式: Agent 依次思考 (顺序 + 间隔)，可观察; await 全部完成。

        用于 hub.step() —— 用户每点一次"单步"推进一个 tick，逐个 Agent 行动，
        便于看清交互节奏。间隔由 AGENT_STEP_DELAY_MS 控制。
        """
        if not self._running:
            return
        step_delay = getattr(getattr(self.hub.config, "simulation", None), "agent_step_delay_ms", 0) / 1000.0
        snapshot = await self.hub.snapshot()
        for agent_id, rt in list(self._agents.items()):
            if rt.busy:
                continue
            await self._safe_tick(agent_id, snapshot)
            if step_delay > 0:
                await asyncio.sleep(step_delay)

    async def _safe_tick(self, agent_id: str, snapshot: dict) -> None:
        try:
            await self._agent_tick(agent_id, snapshot)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            logger.exception("[%s] tick 异常", agent_id)

    async def _agent_tick(self, agent_id: str, snapshot: dict) -> None:
        rt = self._agents.get(agent_id)
        if rt is None:
            return
        rt.busy = True
        try:
            profile = rt.profile
            tasks = await self.hub.task_manager.pending_for(agent_id, profile.role)
            user_msg = self._build_prompt(profile, snapshot, rt.memory, tasks)
            messages: list[dict] = [{"role": "user", "content": user_msg}]
            max_iters = self.hub.config.llm.max_iters
            tick = snapshot.get("tick", 0)
            thought = ""

            # ── 多轮工具循环 ──
            for _ in range(max_iters):
                resp = await self.hub.llm_gateway.chat(profile, messages, tools=profile.tools)
                if resp.error:
                    logger.warning("[%s] LLM 错误: %s", agent_id, resp.error)
                    await self.hub.emit_frontend(
                        {"type": "agent_action", "agent": profile.name,
                         "action": f"(LLM 错误: {resp.error})"}
                    )
                    break
                if resp.content and not thought:
                    thought = resp.content
                if not resp.tool_calls:
                    break  # 纯文本回复，结束本轮

                # 把 assistant 的 tool_calls 入对话，逐个执行并回填 tool 结果
                messages.append({
                    "role": "assistant",
                    "content": resp.content or "",
                    "tool_calls": resp.tool_calls,
                })
                for tc in resp.tool_calls:
                    fn = tc.get("function", {}) if isinstance(tc, dict) else {}
                    name = fn.get("name", "")
                    raw_args = fn.get("arguments", "{}")
                    try:
                        args = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
                    except json.JSONDecodeError:
                        logger.warning("[%s] 工具参数非 JSON: %s", agent_id, raw_args)
                        args = {}
                    result = await self._execute_tool(rt, agent_id, profile, name, args, tick)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.get("id", ""),
                        "content": result,
                    })
            else:
                logger.warning("[%s] 达到 max_iters=%d 仍持续调工具", agent_id, max_iters)

            if thought:
                rt.memory.add(
                    MemoryEntry(id=f"t{tick}-{agent_id}", content=thought, memory_type="reflection")
                )
                await self.hub.emit_frontend(
                    {"type": "agent_message", "sender": profile.name, "content": thought[:200]}
                )
                logger.info("[%s] 思考: %s", profile.name, thought[:120].replace("\n", " "))
        finally:
            rt.busy = False

    # ── Prompt 组装 ──
    @staticmethod
    def _build_prompt(profile: AgentProfile, snapshot: dict, memory: MemoryManager, tasks: list) -> str:
        from aisim.tools import all_tools

        agents = snapshot.get("agents", [])
        team = ", ".join(
            f"{a['name']}({a['role']}, id={a.get('agent_id', a['name'])})" for a in agents
        ) or "无"
        eco = snapshot.get("economy", {})
        recent = "\n".join(f"- {m.content}" for m in memory.recent(5)) or "(无)"
        registered = set(all_tools().keys())
        tools = ", ".join(t for t in profile.tools if t in registered) or "(无)"
        directive = SimulatedAgentRunner._directive(profile, agents, tasks)
        task_lines = (
            "\n".join(f"- [{t.id}] {t.title}：{t.description}" for t in tasks)
            if tasks
            else "(无)"
        )
        return (
            f"Tick {snapshot.get('tick', 0)}。公司: {snapshot.get('company', '')}，"
            f"资金 ${eco.get('capital', 0)}，月烧钱 ${eco.get('monthly_burn', 0)}，"
            f"团队({len(agents)}人): {team}。\n"
            f"{directive}\n"
            f"你的待办任务:\n{task_lines}\n"
            f"近期行动/记忆:\n{recent}\n"
            f"可用工具: {tools}。\n"
            f"请决定这一步的行动并调用工具。可连续调用多个工具，每个工具会返回结果，"
            f"你可基于结果继续行动；无更多动作时回复文本结束。"
        )

    @staticmethod
    def _directive(profile: AgentProfile, agents: list, tasks: list) -> str:
        """按角色/团队/任务现状给具体行动指令 (强引导，避免空转 + 分工)。"""
        roles = {a.get("role") for a in agents}
        if profile.role == "ceo":
            if "hr-director" not in roles:
                return (
                    "⚠️ 公司只有你一人。立即 create_agent 招聘一名 HR Director "
                    '(role="hr-director", department="People", salary=120000)--这是你唯一直接招聘的角色。'
                )
            # HR 已就位: 招工程师/设计师归 HR，CEO 不再 create_agent 招人
            if "senior-engineer" not in roles or "junior-engineer" not in roles:
                return (
                    "HR 已就位。招聘 senior-engineer 与 junior-engineer 是 HR 的职责，"
                    "**你不要 create_agent 招工程师**。用 send_message 给 HR (id 见团队列表) 下达招聘指令，"
                    "本 tick 可先规划项目方向。"
                )
            if "designer" not in roles and len(agents) < 5:
                return (
                    "工程团队已就位。用 send_message 让 HR 招一名 designer (不要自己招)；"
                    "同时用 create_task 给 senior-engineer 派第一个任务。"
                )
            return (
                "团队齐备，**停止招聘**。用 create_task 给工程师派活 "
                "(assignee_role='senior-engineer'，写清 title/description)，每 tick 创建 1 个新任务直到 2-3 个在途。"
            )
        if profile.role == "hr-director":
            missing = []
            if "senior-engineer" not in roles:
                missing.append("senior-engineer")
            if "junior-engineer" not in roles:
                missing.append("junior-engineer")
            if missing:
                return (
                    f"你是 HR，负责招聘。团队缺 {'/'.join(missing)}，"
                    "立即用 create_agent 招聘 (先 senior 再 junior)。"
                )
            if "designer" not in roles and len(agents) < 5:
                return "工程团队齐备，用 create_agent 招一名 designer。"
            return "团队齐备，**停止招聘**。可用 send_message 协助沟通。"
        # 工程师/设计师
        if tasks:
            ids = ", ".join(t.id for t in tasks)
            return (
                f"立即用 complete_task 完成其中一个任务 (task_id 从上面任选: {ids})。"
                "web_search 未接真实搜索 API、write_code/run_tests 是桩，不必调用；"
                "result 写清你实现了什么、产出什么。"
            )
        return "暂无待办任务；用 send_message 向 CEO 请求任务。"

    # ── 工具执行 (返回结果字符串供 LLM 下一轮参考) ──
    async def _execute_tool(
        self, rt: _AgentRuntime, agent_id: str, profile: AgentProfile,
        name: str, args: dict, tick: int,
    ) -> str:
        rt.memory.add(MemoryEntry(
            id=f"tool-{tick}-{name}-{agent_id}-{len(rt.memory.recent(99))}",
            content=f"调用工具 {name}({args})", memory_type="action",
        ))

        if name == "create_agent":
            r = await self.hub.create_agent(
                name=args.get("name", "Unnamed"), role=args.get("role", "junior-engineer"),
                department=args.get("department", "General"), salary=int(args.get("salary", 0) or 0),
                personality=args.get("personality"), report_to=args.get("report_to") or agent_id,
            )
            await self.hub.emit_frontend(
                {"type": "agent_action", "agent": profile.name,
                 "action": f"create_agent -> {r.get('name', '')}({r.get('role', '')})"})
            return f"已创建 Agent {r.get('name', '')} ({r.get('role', '')}), agent_id={r.get('agent_id', '')}"

        if name == "send_message":
            content = args.get("content", "")
            recipient = args.get("recipient")
            if recipient:
                await self.hub.message_bus.send_dm(agent_id, recipient, content)
                await self.hub.emit_frontend(
                    {"type": "agent_message", "sender": profile.name, "content": content[:200]})
                return f"已向 {recipient} 发送消息"
            await self.hub.message_bus.broadcast_announcement(agent_id, content)
            await self.hub.emit_frontend(
                {"type": "agent_message", "sender": profile.name, "content": content[:200]})
            return "已广播公告"

        if name == "call_meeting":
            participants = args.get("participants", [])
            minutes = await self.hub.call_meeting(agent_id, args.get("topic", ""), participants)
            await self.hub.emit_frontend(
                {"type": "agent_action", "agent": profile.name,
                 "action": f"call_meeting: {args.get('topic', '')}"})
            return f"会议纪要:\n{minutes[:400]}"

        if name == "create_task":
            t = await self.hub.create_task(
                title=args.get("title", "Untitled"), description=args.get("description", ""),
                assignee_role=args.get("assignee_role", ""), assignee=args.get("assignee", ""),
                project=args.get("project", ""), priority=args.get("priority", "normal"),
                created_by=agent_id,
            )
            await self.hub.emit_frontend(
                {"type": "agent_action", "agent": profile.name,
                 "action": f"create_task -> {t.get('title', '')}"})
            return (f"已创建任务 '{t.get('title', '')}' (id={t.get('id', '')}), "
                    f"派给 {t.get('assignee_role', '') or t.get('assignee', '')}")

        if name == "complete_task":
            r = await self.hub.complete_task(
                task_id=args.get("task_id", ""), agent_id=agent_id, result=args.get("result", ""))
            await self.hub.emit_frontend(
                {"type": "agent_action", "agent": profile.name,
                 "action": f"complete_task {args.get('task_id')}"})
            return "任务已完成" if r else f"任务 {args.get('task_id')} 不存在或已完成"

        if name == "share_skill":
            await self.hub.share_skill(
                source_agent_id=agent_id, name=args.get("name", ""),
                prompt_injection=args.get("prompt_injection", ""), target_role=args.get("target_role", ""))
            await self.hub.emit_frontend(
                {"type": "agent_action", "agent": profile.name,
                 "action": f"share_skill -> {args.get('target_role')}: {args.get('name')}"})
            return f"已分享 Skill '{args.get('name', '')}' 给 {args.get('target_role', '')}"

        if name == "learn_skill":
            r = await self.hub.learn_skill(agent_id, args.get("query", ""))
            await self.hub.emit_frontend(
                {"type": "agent_action", "agent": profile.name,
                 "action": f"learn_skill: {args.get('query')}"})
            learned = r.get("name") if isinstance(r, dict) and r.get("name") else None
            return f"已学习 Skill: {learned}" if learned else f"未找到与 '{args.get('query', '')}' 相关的 Skill"

        # 未实现/桩工具 (web_search / write_code / write_file 等)
        await self.hub.emit_frontend(
            {"type": "agent_action", "agent": profile.name, "action": name, "target": args.get("target")})
        logger.info("[%s] 桩工具 %s(%s)", profile.name, name, args)
        return f"工具 {name} 未实现或无有效返回 (桩)"
