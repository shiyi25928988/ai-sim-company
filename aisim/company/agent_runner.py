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
import shutil
from dataclasses import dataclass, field
from pathlib import Path

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
                mcp_tools = self.hub.mcp_manager.list_all_tools()
                resp = await self.hub.llm_gateway.chat(profile, messages, tools=profile.tools + mcp_tools)
                if resp.error:
                    logger.warning("[%s] LLM 错误: %s", agent_id, resp.error)
                    await self.hub.emit_frontend(
                        {"type": "agent_action", "agent": profile.name,
                         "action": f"(LLM error: {resp.error})"}
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
    def _build_prompt(self, profile: AgentProfile, snapshot: dict, memory: MemoryManager, tasks: list) -> str:
        from aisim.tools import all_tools

        company = self.hub.config.company
        agents = snapshot.get("agents", [])
        team = ", ".join(
            f"{a['name']}({a['role']}, id={a.get('agent_id', a['name'])})" for a in agents
        ) or "(none)"
        eco = snapshot.get("economy", {})
        query = f"{company.business_description} {' '.join(t.title for t in tasks)}".strip()
        recent = "\n".join(f"- {m.content}" for m in memory.recall(query, 5)) or "(none)"
        registered = set(all_tools().keys())
        tool_names = [t for t in profile.tools if t in registered]
        tool_names.extend(t["function"]["name"] for t in self.hub.mcp_manager.list_all_tools())
        tools = ", ".join(tool_names) or "(none)"
        directive = SimulatedAgentRunner._directive(profile, agents, tasks)
        task_lines = (
            "\n".join(f"- [{t.id}] {t.title}: {t.description}" for t in tasks)
            if tasks
            else "(none)"
        )
        biz = company.business_description
        budget = company.monthly_budget
        budget_line = f" Budget cap: ${budget}/mo." if budget else ""
        return (
            f"Tick {snapshot.get('tick', 0)}. Company: {snapshot.get('company', '')}."
            f"{' Business: ' + biz if biz else ''}\n"
            f"Capital ${eco.get('capital', 0)}, monthly burn ${eco.get('monthly_burn', 0)}.{budget_line}"
            f" Team ({len(agents)}): {team}.\n"
            f"{directive}\n"
            f"Your pending tasks:\n{task_lines}\n"
            f"Recent actions/memory:\n{recent}\n"
            f"Available tools: {tools}.\n"
            f"Decide your action this step and call tools. You may call multiple tools in sequence; "
            f"each returns a result you can act on. When you have no further actions, reply with text to end the turn."
        )

    @staticmethod
    def _directive(profile: AgentProfile, agents: list, tasks: list) -> str:
        """Give concrete action directives based on role/team/task state (strong guidance, to avoid spinning + divide labor)."""
        roles = {a.get("role") for a in agents}
        if profile.role == "ceo":
            if "hr-director" not in roles:
                return (
                    "⚠️ You are the only one in the company. Immediately create_agent to hire an HR Director "
                    '(role="hr-director", department="People", salary=120000) - this is the only role you hire directly.'
                )
            # HR is in place: hiring engineers/designers is HR's job, CEO no longer create_agent to hire
            if "senior-engineer" not in roles or "junior-engineer" not in roles:
                return (
                    "HR is in place. Hiring senior-engineer and junior-engineer is HR's job. "
                    "**Do not create_agent to hire engineers yourself.** Use send_message to instruct HR (id in team list) to hire; "
                    "this tick you may plan project direction first."
                )
            if "designer" not in roles and len(agents) < 5:
                return (
                    "Engineering team is in place. Use send_message to have HR hire a designer (don't hire yourself); "
                    "also use create_task to assign the first task to a senior-engineer."
                )
            return (
                "Team is complete, **stop hiring**. Use create_task to assign work to engineers "
                "(assignee_role='senior-engineer', clear title/description); create 1 new task per tick until 2-3 are in flight."
            )
        if profile.role == "hr-director":
            missing = []
            if "senior-engineer" not in roles:
                missing.append("senior-engineer")
            if "junior-engineer" not in roles:
                missing.append("junior-engineer")
            if missing:
                return (
                    f"You are HR, responsible for hiring. The team is missing {'/'.join(missing)}; "
                    "immediately use create_agent to hire (senior first, then junior)."
                )
            if "designer" not in roles and len(agents) < 5:
                return "Engineering team is complete; use create_agent to hire a designer."
            return "Team is complete, **stop hiring**. You may use send_message to help with communication."
        # Engineers / designers
        if tasks:
            ids = ", ".join(t.id for t in tasks)
            return (
                f"Immediately use complete_task to finish one of the tasks (pick any task_id from above: {ids}). "
                "web_search has no real search API backing it, and write_code/run_tests are stubs - no need to call them; "
                "write in result what you implemented and what you produced."
            )
        return "No pending tasks; use send_message to ask the CEO for work."

    # ── Tool execution (returns a result string for the LLM's next turn) ──
    async def _execute_tool(
        self, rt: _AgentRuntime, agent_id: str, profile: AgentProfile,
        name: str, args: dict, tick: int,
    ) -> str:
        rt.memory.add(MemoryEntry(
            id=f"tool-{tick}-{name}-{agent_id}-{len(rt.memory.recent(99))}",
            content=f"Called tool {name}({args})", memory_type="action",
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
            return f"Created Agent {r.get('name', '')} ({r.get('role', '')}), agent_id={r.get('agent_id', '')}"

        if name == "send_message":
            content = args.get("content", "")
            recipient = args.get("recipient")
            if recipient:
                await self.hub.message_bus.send_dm(agent_id, recipient, content)
                await self.hub.emit_frontend(
                    {"type": "agent_message", "sender": profile.name, "content": content[:200]})
                return f"Sent message to {recipient}"
            await self.hub.message_bus.broadcast_announcement(agent_id, content)
            await self.hub.emit_frontend(
                {"type": "agent_message", "sender": profile.name, "content": content[:200]})
            return "Broadcast announcement"

        if name == "call_meeting":
            participants = args.get("participants", [])
            minutes = await self.hub.call_meeting(agent_id, args.get("topic", ""), participants)
            await self.hub.emit_frontend(
                {"type": "agent_action", "agent": profile.name,
                 "action": f"call_meeting: {args.get('topic', '')}"})
            return f"Meeting minutes:\n{minutes[:400]}"

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
            return (f"Created task '{t.get('title', '')}' (id={t.get('id', '')}), "
                    f"assigned to {t.get('assignee_role', '') or t.get('assignee', '')}")

        if name == "complete_task":
            r = await self.hub.complete_task(
                task_id=args.get("task_id", ""), agent_id=agent_id, result=args.get("result", ""))
            await self.hub.emit_frontend(
                {"type": "agent_action", "agent": profile.name,
                 "action": f"complete_task {args.get('task_id')}"})
            return "Task completed" if r else f"Task {args.get('task_id')} does not exist or is already completed"

        if name == "share_skill":
            await self.hub.share_skill(
                source_agent_id=agent_id, name=args.get("name", ""),
                prompt_injection=args.get("prompt_injection", ""), target_role=args.get("target_role", ""))
            await self.hub.emit_frontend(
                {"type": "agent_action", "agent": profile.name,
                 "action": f"share_skill -> {args.get('target_role')}: {args.get('name')}"})
            return f"Shared Skill '{args.get('name', '')}' with {args.get('target_role', '')}"

        if name == "learn_skill":
            r = await self.hub.learn_skill(agent_id, args.get("query", ""))
            await self.hub.emit_frontend(
                {"type": "agent_action", "agent": profile.name,
                 "action": f"learn_skill: {args.get('query')}"})
            learned = r.get("name") if isinstance(r, dict) and r.get("name") else None
            return f"Learned Skill: {learned}" if learned else f"No Skill found matching '{args.get('query', '')}'"

        if name == "find_skill":
            results = await self.hub.find_skill(args.get("query", ""))
            if not results:
                return "No skills found matching the query."
            return "Found skills:\n" + "\n".join(
                f"- {r['name']} [{r['level']}] scope={r['scope']}: {r['prompt_injection'][:80]}"
                for r in results
            )

        if name == "create_skill":
            r = await self.hub.create_skill(
                name=args.get("name", ""),
                description=args.get("description", ""),
                prompt_injection=args.get("prompt_injection", ""),
                category=args.get("category", "technical"),
                level=args.get("level", "company"),
                scope=args.get("scope", []),
                created_by=profile.name,
            )
            await self.hub.emit_frontend(
                {"type": "agent_action", "agent": profile.name,
                 "action": f"create_skill {r.get('name', '')}"})
            return f"Created skill '{r.get('name', '')}' (level={r.get('level', '')})"

        if name.startswith("mcp_"):
            return await self.hub.mcp_manager.call_tool(name, args)

        if name in ("write_file", "read_file", "list_files"):
            path = args.get("path", "").lstrip("/")
            scope = args.get("scope", "shared")
            base = Path(self.hub.config.company.workspace_dir)
            sub = agent_id if scope == "personal" else "shared"
            root = (base / sub).resolve()
            full = (root / path).resolve()
            if not str(full).startswith(str(root)):
                return f"Path traversal blocked: {path}"
            if name == "write_file":
                content = args.get("content", "")
                full.parent.mkdir(parents=True, exist_ok=True)
                full.write_text(content, encoding="utf-8")
                await self.hub.emit_frontend(
                    {"type": "agent_action", "agent": profile.name,
                     "action": f"write_file {sub}/{path}"})
                return f"Wrote {len(content)} chars to {sub}/{path}"
            if name == "read_file":
                if not full.exists():
                    return f"File not found: {path}"
                return full.read_text(encoding="utf-8", errors="replace")[:4000]
            # list_files
            if not full.exists():
                return f"Dir not found: {path}"
            files = [f"{p.name}/" if p.is_dir() else p.name for p in sorted(full.iterdir())]
            return ", ".join(files) if files else "(empty)"

        if name == "run_claude_code":
            if not self.hub.config.llm.claude_code_enabled:
                return "claude code is disabled; enable it in /settings."
            claude_path = shutil.which("claude")
            if not claude_path:
                return "claude code CLI not found in PATH."
            prompt = args.get("prompt", "")
            cwd = str(Path(self.hub.config.company.workspace_dir).resolve())
            await self.hub.emit_frontend(
                {"type": "agent_action", "agent": profile.name,
                 "action": f"run_claude_code: {prompt[:60]}"})
            try:
                proc = await asyncio.create_subprocess_exec(
                    claude_path, "-p", prompt,
                    cwd=cwd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
            except asyncio.TimeoutError:
                proc.kill()
                return "claude code timed out (120s)."
            except Exception as e:  # noqa: BLE001
                return f"claude code failed: {e}"
            out = stdout.decode("utf-8", errors="replace")[:2000] if stdout else ""
            if out:
                return f"claude code output:\n{out}"
            err = stderr.decode("utf-8", errors="replace")[:300] if stderr else ""
            return f"claude code produced no output (stderr: {err})"

        # Unimplemented / stub tools (web_search / write_code / write_file etc.)
        await self.hub.emit_frontend(
            {"type": "agent_action", "agent": profile.name, "action": name, "target": args.get("target")})
        logger.info("[%s] 桩工具 %s(%s)", profile.name, name, args)
        return f"Tool {name} is not implemented or has no valid return (stub)"
