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
init.bat                         :: checks Python/Node/MCP tools, installs deps, builds frontend
copy .env.example .env           :: fill in LLM_API_KEY (+ optional LLM_MODEL / LLM_BASE_URL)
```

### Run

```bat
start.bat                        :: start backend (:8000) + frontend (:3000)
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

### `.env` (environment variables)

Copy `.env.example` to `.env` and fill in. The backend auto-loads it on startup. These vars are referenced by `config/company.yaml` via `${VAR}` placeholders.

| Variable | Required | Default | Description |
|---|---|---|---|
| `LLM_API_KEY` | yes | - | LLM API key (configured once; agents never see it). |
| `LLM_PROVIDER` | no | `openai` | Interface type: `openai` (OpenAI-compatible `/chat/completions`) or `anthropic` (native `/v1/messages`). |
| `LLM_MODEL` | no | `gpt-4o-mini` | Default model for all agents. |
| `LLM_BASE_URL` | no | (official OpenAI) | OpenAI-compatible endpoint. DeepSeek: `https://api.deepseek.com/v1`; Zhipu: `https://open.bigmodel.cn/api/paas/v4`; one-api: `http://localhost:3000/v1`. |
| `LLM_TOOLS_ENABLED` | no | `true` | Enable function-calling (agent tools). `false` if the endpoint doesn't support tools (agents still think, plain text). |
| `LLM_MAX_ITERS` | no | `3` | Max LLM<->tool loop rounds per agent per tick. `1` = cheapest; `3` = can chain multiple tools. |
| `LLM_DAILY_BUDGET` | no | `2000000` | Daily token budget (cost cap). `0`/negative = unlimited. |
| `LLM_RPM_LIMIT` | no | `0` | Requests-per-minute cap. `0` = unlimited. Set to match your API key's rate limit to avoid 429s. |
| `AGENT_BACKEND` | no | `simulated` | `simulated` (local dev) or `docker` (production). |
| `TICK_INTERVAL_MS` | no | `5000` | Simulation tick interval (ms). Larger = slower clock, less LLM cost. |
| `SIM_AUTO_START` | no | `false` | `true` = auto-run on startup; `false` = paused (manual Play). |
| `AGENT_THINK_EVERY` | no | `1` | Agent thinks once every N ticks. `1` = every tick; larger saves cost. |
| `AGENT_STEP_DELAY_MS` | no | `800` | Interval between agents in step mode (ms). |

#### LLM interface

Two interface types are supported, selected by `LLM_PROVIDER`:

- **`openai`** (default) - OpenAI-compatible `/chat/completions`. Works with OpenAI, DeepSeek, Zhipu, Moonshot, Qwen, one-api/new-api proxies, OpenRouter, etc. Set `LLM_BASE_URL` to the endpoint.
- **`anthropic`** - Anthropic native `/v1/messages`. Direct connection to Claude official API (`api.anthropic.com`). Leave `LLM_BASE_URL` empty.

The system uses OpenAI message format internally; when `anthropic` is selected, messages/tools are converted automatically on the wire.

**DeepSeek example:**
```
LLM_API_KEY=sk-...
LLM_MODEL=deepseek-v4-flash
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_PROVIDER=openai
LLM_RPM_LIMIT=60
```

**Anthropic (Claude) example:**
```
LLM_API_KEY=sk-ant-...
LLM_MODEL=claude-sonnet-5
LLM_PROVIDER=anthropic
LLM_BASE_URL=
```

### `config/company.yaml`

Business (name / description / budget / workspace_dir), CEO, LLM routing, MCP servers. The `/setup` page writes the `company` section; MCP servers are managed on `/mcp`.
