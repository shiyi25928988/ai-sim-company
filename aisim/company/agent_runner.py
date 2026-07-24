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
from aisim.shared.models import AgentProfile, AgentStatus, TaskStatus

logger = logging.getLogger(__name__)


@dataclass
class _AgentRuntime:
    profile: AgentProfile
    memory: MemoryManager = field(default_factory=lambda: MemoryManager(""))
    busy: bool = False
    idle_count: int = 0


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
            # non-management roles with no task: after 2 consecutive idle ticks, lay off
            if not tasks and profile.role not in ("ceo", "hr-director", "product-manager"):
                rt.idle_count += 1
                if rt.idle_count >= 5:
                    await self.hub.remove_agent(agent_id)
                    logger.info("[%s] 连续 %d 轮无任务，解雇", profile.name, rt.idle_count)
                else:
                    logger.info("[%s] 无任务，idle %d/5", profile.name, rt.idle_count)
                return
            rt.idle_count = 0  # has task, reset idle counter
            # if already working on a task, don't claim a new one (focus until complete)
            has_in_progress = any(
                t.assignee == agent_id and t.status == TaskStatus.IN_PROGRESS for t in tasks
            )
            if not has_in_progress:
                unclaimed = [t for t in tasks if t.assignee == ""]
                if unclaimed:
                    await self.hub.task_manager.claim(unclaimed[0].id, agent_id)
                    await self.hub.agent_manager.set_status(agent_id, AgentStatus.WORKING)
                    tasks = await self.hub.task_manager.pending_for(agent_id, profile.role)
            user_msg = self._build_prompt(profile, snapshot, rt.memory, tasks)
            messages: list[dict] = [{"role": "user", "content": user_msg}]
            max_iters = self.hub.config.llm.max_iters
            tick = snapshot.get("tick", 0)
            thought = ""

            # ── Multi-turn tool loop with quality controls ──
            tool_call_count = 0
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
                    # Plain text reply with no tool calls - done with this turn
                    if thought and tool_call_count == 0:
                        thought = thought  # Pure reflection turn - nothing to do
                    break

                tool_call_count += 1

                # Add the assistant's tool_calls to the conversation, execute each and feed results back
                # Wrap with structured tags and auto-summary for long outputs
                assistant_msg = {
                    "role": "assistant",
                    "content": resp.content or "",
                    "tool_calls": resp.tool_calls,
                }
                messages.append(assistant_msg)

                for tc in resp.tool_calls:
                    fn = tc.get("function", {}) if isinstance(tc, dict) else {}
                    name = fn.get("name", "")
                    raw_args = fn.get("arguments", "{}")
                    try:
                        args = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
                    except json.JSONDecodeError:
                        args = {}
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc.get("id", ""),
                            "content": f"""<tool_error>
Invalid JSON in tool arguments. Fix the syntax and retry - make sure arguments
is a valid JSON object string, e.g. {{\"name\": \"value\"}}.
Raw input: {str(raw_args)[:200]}
</tool_error>"""
                        })
                        continue

                    result = await self._execute_tool(rt, agent_id, profile, name, args, tick)

                    # Result wrapping: add structure tags and auto-summarize very long output
                    if "failed" in result.lower() or "error" in result.lower() or "not found" in result.lower():
                        wrapped = f"""<tool_error>
Tool: {name}
Error: {result}

How to fix:
1. Read the error message carefully
2. Check if you have correct parameters (missing required fields, wrong types)
3. If a resource is missing, use a lookup tool first (e.g. find_skill before learn_skill)
4. Retry at most ONCE - if it fails again, try a different approach
</tool_error>"""
                    else:
                        if len(result) > 1200:
                            # Auto-summary: keep head + tail
                            wrapped = f"""<tool_result>
Tool: {name}
Result (truncated, {len(result)} chars total):
--- START HEAD ---
{result[:600]}
--- START TAIL ---
{result[-600:]}
--- END ---
Full content was written to the workspace. Extract key takeaways and proceed with your next step.
</tool_result>"""
                        else:
                            wrapped = f"""<tool_result>
Tool: {name}
{result}
</tool_result>"""

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.get("id", ""),
                        "content": wrapped,
                    })
            else:
                logger.warning("[%s] 达到 max_iters=%d 仍持续调工具", agent_id, max_iters)
                # Always end the turn cleanly after max iterations
                if not thought:
                    thought = f"(Tool loop reached max iterations after {max_iters} tool calls. Turn completed.)"

            if thought:
                rt.memory.add(
                    MemoryEntry(id=f"t{tick}-{agent_id}", content=thought, memory_type="reflection")
                )
                await self.hub.emit_frontend(
                    {"type": "agent_message", "sender": profile.name, "content": thought[:200]}
                )
                logger.info("[%s] 思考: %s", profile.name, thought[:120].replace("\n", " "))
            # Note: directives are consumed in _build_prompt and cleared there (before LLM call)
            #   not here. This avoids a race: if a directive comes in during tool execution, it
            #   would be dropped before being seen if we cleared here after build_prompt ran.
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
        directive_lines = ""
        if profile.role == "ceo" and getattr(self.hub, "directives", None):
            directive_lines = "\n\n⚠️ BOARD/USER DIRECTIVE (ACT ON THESE THIS TURN):\n" + "\n".join(
                f"- {d}" for d in self.hub.directives
            ) + "\n"
            # Consume immediately after reading to avoid race condition (injection happens before tool loop)
            self.hub.directives.clear()

        # Determine immediate priority based on task state
        pending_count = len(tasks)
        assigned_to_me = [t for t in tasks if t.assignee == profile.agent_id]
        claimable = [t for t in tasks if not t.assignee and t.assignee_role == profile.role]

        priority_hint = ""
        if assigned_to_me:
            priority_hint = f"\nYour assigned tasks ({len(assigned_to_me)}):\n" + "\n".join(
                f"  - [{t.id}] {t.title} (status: {t.status})" for t in assigned_to_me
            )
        elif claimable and pending_count < 10:
            priority_hint = f"\nUnclaimed tasks for your role ({profile.role}): {len(claimable)} - pick one using complete_task"
        elif not tasks:
            priority_hint = "\nNo pending tasks. Either create_task for the team or send_message to coordinate."

        return (
            f"Tick {snapshot.get('tick', 0)}. Company: {snapshot.get('company', '')}."
            f"{' Business: ' + biz if biz else ''}\n"
            f"Capital ${eco.get('capital', 0)}, monthly burn ${eco.get('monthly_burn', 0)}.{budget_line}"
            f" Team ({len(agents)}): {team}.\n"
            f"{directive}\n"
            f"{priority_hint}\n"
            f"Recent actions/memory:\n{recent}\n"
            f"Available tools: {tools}.\n\n"
            f"CRITICAL INSTRUCTIONS (FOLLOW STRICTLY):\n"
            f"1. THINK FIRST: Before calling any tool, write out your reasoning in text.\n"
            f"2. ONE TOOL AT A TIME: Do not call tools in parallel. Execute then evaluate.\n"
            f"3. CHECK RESULTS: Read the full tool_result/tool_error tags before deciding your next step.\n"
            f"4. FINISH WHEN DONE: When you have acted and have no more steps, reply with a summary in text.\n"
            f"5. NO PLACEHOLDERS: When writing code/designs, write working content, not TODOs.\n"
            f"6. MAX 3 TOOL CALLS PER TURN. If not done by then, summarize your progress and end the turn."
            f"{directive_lines}"
        )

    @staticmethod
    def _directive(profile: AgentProfile, agents: list, tasks: list) -> str:
        """Give concrete action directives based on role/team/task state (PM-driven hiring flow)."""
        roles = {a.get("role") for a in agents}
        if profile.role == "ceo":
            if "hr-director" not in roles:
                return (
                    "⚠️ You are the only one. Immediately create_agent to hire an HR Director "
                    '(role="hr-director", department="People", salary=120000).'
                )
            if "product-manager" not in roles:
                return (
                    "HR is in place. Use send_message to instruct HR to hire a Product Manager next "
                    '(role="product-manager", department="Product", salary≈130000) - the PM will plan the product and tell HR what roles to hire.'
                )
            return (
                "HR + PM are in place. Focus on strategy: use send_message to coordinate, "
                "call_meeting to align. Let the PM create product tasks - don't create_task yourself."
            )
        if profile.role == "hr-director":
            if "product-manager" not in roles:
                return (
                    'Hire a Product Manager first (role="product-manager", department="Product", salary≈130000) - '
                    "the PM will assess the business and raise hiring requests to you."
                )
            hiring_tasks = [t for t in tasks if "hiring" in (t.title or "").lower()]
            if hiring_tasks:
                reqs = "; ".join(t.title for t in hiring_tasks)
                return (
                    f"PM has hiring requests: {reqs}. create_agent per request (use the role/scope in the task), "
                    "then complete_task to mark it fulfilled. Don't hire beyond what the PM requested."
                )
            return (
                "PM is in place but no hiring requests yet. Wait for the PM to assess needs - don't hire speculatively."
            )
        if profile.role == "product-manager":
            return (
                "Analyze the business description and decide what roles/skills the product needs. "
                "If not done yet, create hiring-request tasks for HR (assignee_role='hr-director', "
                "title='Hiring request: need <count> <role> - <reason>', description with scope/skills) - one per role. "
                "Then create product tasks (features/milestones, assignee_role='senior-engineer' or 'designer')."
            )
        if profile.role == "senior-engineer":
            if tasks:
                ids = ", ".join(t.id for t in tasks)
                return (
                    f"Pick up a task (task_id from: {ids}). Use run_claude_code to implement it - pass the task description "
                    "and any relevant design docs (read_file from workspace/skills/ or shared/) in the prompt. "
                    "Then run_claude_code again to test/verify. Use code_review on team members' files. "
                    "complete_task only after verification - describe what you delivered and how you verified it."
                )
            return "No pending tasks; use code_review to review the team's work, or ask the PM for more."
        if profile.role == "junior-engineer":
            if tasks:
                ids = ", ".join(t.id for t in tasks)
                return (
                    f"Pick up a task (task_id from: {ids}). Use run_claude_code to implement it - pass the task description "
                    "and relevant design docs in the prompt. Then run_claude_code to test/verify before complete_task. "
                    "If stuck, ask_for_help. Describe what you delivered and how you verified it in complete_task."
                )
            return "No pending tasks; use send_message to ask a senior engineer or the PM for work."
        if profile.role == "designer":
            if tasks:
                ids = ", ".join(t.id for t in tasks)
                return (
                    f"Pick up a task (task_id from: {ids}). Use run_claude_code to create design docs/assets - pass the task "
                    "description and any existing design context in the prompt. Verify the output meets requirements, then complete_task."
                )
            return "No pending tasks; use send_message to ask the PM for work."
        return "No pending tasks; use send_message to ask the PM for work."

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

        if name == "code_review":
            path = args.get("path", "").lstrip("/")
            scope = args.get("scope", "shared")
            base = Path(self.hub.config.company.workspace_dir)
            sub = agent_id if scope == "personal" else "shared"
            root = (base / sub).resolve()
            full = (root / path).resolve()
            if not str(full).startswith(str(root)) or not full.exists() or full.is_dir():
                return f"File not found: {path}"
            content = full.read_text(encoding="utf-8", errors="replace")[:4000]
            review_prompt = (
                f"Review this file ({scope}/{path}) for correctness, edge cases, readability, and test coverage. "
                "List issues concisely; if it looks correct, say so.\n\n```\n" + content + "\n```"
            )
            resp = await self.hub.llm_gateway.chat(
                profile, [{"role": "user", "content": review_prompt}], tools=[]
            )
            await self.hub.emit_frontend(
                {"type": "agent_action", "agent": profile.name, "action": f"code_review {scope}/{path}"})
            return f"Review of {scope}/{path}:\n{resp.content or resp.error or '(no response)'}"

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
                if full.exists() and full.is_dir():
                    return f"Cannot write to '{sub}/{path}': it is a directory, not a file. Specify a filename inside it."
                full.parent.mkdir(parents=True, exist_ok=True)
                full.write_text(content, encoding="utf-8")
                await self.hub.emit_frontend(
                    {"type": "agent_action", "agent": profile.name,
                     "action": f"write_file {sub}/{path}"})
                return f"Wrote {len(content)} chars to {sub}/{path}"
            if name == "read_file":
                if not full.exists():
                    return f"File not found: {path}"
                if full.is_dir():
                    return f"'{sub}/{path}' is a directory - call list_files on it instead."
                return full.read_text(encoding="utf-8", errors="replace")[:4000]
            # list_files
            if not full.exists():
                return f"Dir not found: {path}"
            if not full.is_dir():
                return f"'{sub}/{path}' is a file - call read_file to read it."
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
                    claude_path, "-p", prompt, "--dangerously-skip-permissions",
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
