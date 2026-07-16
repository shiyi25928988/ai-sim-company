"""SimulatedAgentRunner - hosts the Agent main loop inside the Hub in simulated mode.

Design trade-off: simulated mode has no real Agent container (hermes unavailable), so the Hub process
runs a tick loop for each simulated Agent, calling LLMGateway.chat directly in-process
(equivalent to "going through the Hub LLM Gateway"). In docker mode Agents run in their own containers
and do not go through this runner.

Multi-turn tool loop (ReAct / OpenAI tools loop):
  Each Tick:
    snapshot -> assemble prompt -> [LLM.chat -> if there are tool_calls, execute and feed results back -> chat again]
    repeat until there are no tool_calls or max_iters is reached. Tool results are fed back to the LLM, so web_search/
    write_file etc. can be used in a "search/write then look at the result" fashion (even though most tools are still stubs).
The busy flag prevents overlapping ticks for the same Agent (skips when the LLM call is slower than the tick interval).
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
    """The simulated Agent main loop hosted inside the Hub."""

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

    # ── Registration ──
    def register(self, profile: AgentProfile) -> None:
        self._agents[profile.agent_id] = _AgentRuntime(
            profile=profile, memory=MemoryManager(profile.agent_id)
        )

    def unregister(self, agent_id: str) -> None:
        self._agents.pop(agent_id, None)

    def has(self, agent_id: str) -> bool:
        return agent_id in self._agents

    def recent_memory(self, agent_id: str, limit: int = 5) -> list[dict]:
        """An Agent's recent thoughts/actions (for the frontend AgentPanel to display)."""
        rt = self._agents.get(agent_id)
        if not rt:
            return []
        return [{"content": m.content, "type": m.memory_type} for m in rt.memory.recent(limit)]

    # ── Tick ──
    async def on_tick(self, tick: int) -> None:
        """Each simulation Tick (play mode): concurrently dispatch non-busy Agents to think (fire-and-forget, fast)."""
        if not self._running:
            return
        # Agents think every N ticks (1=every tick; cost control). The hub still pushes snapshot/economy.
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
        """Step mode: Agents think one by one (sequential + interval), observable; awaits all to finish.

        Used by hub.step() -- each time the user clicks "step" one tick advances and Agents act one by one,
        making it easy to see the interaction rhythm. The interval is controlled by AGENT_STEP_DELAY_MS.
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

            # ── Multi-turn tool loop ──
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
                    break  # plain-text reply, end this turn

                # Add the assistant's tool_calls to the conversation, execute each and feed tool results back
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

    # ── Prompt assembly ──
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
        """Give concrete action directives based on role/team/task state (strong guidance, to avoid spinning + divide labor)."""
        roles = {a.get("role") for a in agents}
        if profile.role == "ceo":
            if "hr-director" not in roles:
                return (
                    "⚠️ 公司只有你一人。立即 create_agent 招聘一名 HR Director "
                    '(role="hr-director", department="People", salary=120000)--这是你唯一直接招聘的角色。'
                )
            # HR is in place: hiring engineers/designers is HR's job, CEO no longer create_agent to hire
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
        # Engineers / designers
        if tasks:
            ids = ", ".join(t.id for t in tasks)
            return (
                f"立即用 complete_task 完成其中一个任务 (task_id 从上面任选: {ids})。"
                "web_search 未接真实搜索 API、write_code/run_tests 是桩，不必调用；"
                "result 写清你实现了什么、产出什么。"
            )
        return "暂无待办任务；用 send_message 向 CEO 请求任务。"

    # ── Tool execution (returns a result string for the LLM's next turn) ──
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

        # Unimplemented / stub tools (web_search / write_code / write_file etc.)
        await self.hub.emit_frontend(
            {"type": "agent_action", "agent": profile.name, "action": name, "target": args.get("target")})
        logger.info("[%s] 桩工具 %s(%s)", profile.name, name, args)
        return f"工具 {name} 未实现或无有效返回 (桩)"
