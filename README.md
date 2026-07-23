# ai-sim-company

> Multi-agent AI company simulation. Configure a business, and a CEO (LLM-driven) autonomously runs it - hiring, delegating, meeting, producing - while you watch on a real-time dashboard.

[中文](./README.zh-CN.md)

## Principle

You set the business (name / description / budget). A CEO agent then runs the company autonomously via an LLM:

- **CEO** hires an HR Director, then focuses on strategy and delegation.
- **HR** hires a Product Manager first.
- **PM** analyzes the business and tells HR what roles the product needs (e.g. "2 senior engineers, 1 designer").
- **HR** hires per the PM's requests.
- **Engineers / Designers** pick up tasks, produce files (code / docs / assets) in a shared workspace, verify with tests/reviews, then mark work done.
- Everyone communicates via messages and meetings; the simulation clock advances; the dashboard shows it live.

Agents make real decisions by calling tools each tick (`create_agent` / `send_message` / `create_task` / `call_meeting` / `write_file` / `run_claude_code` / `code_review` / `find_skill` / `mcp_*`). You're an observer - you don't control agents directly, but you can send the CEO a directive from the console at any time.

The LLM API key is configured once; agents never see it.

## Usage

### One-time setup

```bat
init.bat                         :: checks Python/Node/Redis, installs deps, builds frontend
copy .env.example .env           :: fill in LLM_API_KEY (+ optional LLM_MODEL / LLM_BASE_URL)
```

### Run

```bat
start.bat                        :: start Redis + backend (:8000) + frontend (:3000)
stop.bat                         :: stop services
reset.bat                        :: clear data and start fresh
```

Open http://localhost:3000:

1. **/setup** - configure the business (name, description, capital, monthly budget, workspace dir) -> Apply (resets the simulation, re-seeds the CEO).
2. **Console (/)** - ▶ Play / ⏭ Step, watch logs (filterable), tasks, agent panel. Use **📢 CEO Directive** to send instructions to the CEO.
3. **/agents** - view the team, hire agents, click into agent detail.
4. **/skills** - manage skills: create / paste JSON / install from URL / upload .zip (SKILL.md + .py). Edit / delete. Agents inherit skills and can find / create / share them.
5. **/mcp** - configure external MCP servers (stdio / sse / streamableHttp). Their tools become available to all agents.
6. **/files** - browse the workspace (agent-produced code / docs / assets).
7. **/dashboard** - cash flow, LLM usage, team, project board.
8. **/settings** - LLM config (read-only), Claude Code enable toggle.

### CEO Directive

On the console, click **📢 CEO Directive** -> type an instruction (e.g. "add a task: implement login", "focus on performance this week") -> the CEO acts on it next tick.

## Configuration

- **`.env`** - `LLM_API_KEY` (required), `LLM_MODEL` / `LLM_BASE_URL` / `LLM_PROVIDER` (for OpenAI-compatible endpoints like DeepSeek), Redis, simulation speed.
- **`config/company.yaml`** - business (name / description / budget / workspace_dir), CEO, LLM routing, MCP servers. The `/setup` page writes the `company` section.
