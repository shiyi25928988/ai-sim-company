# ai-sim-company

> Multi-agent AI company simulation — configure the business and budget, a CEO (LLM-driven) autonomously hires / assigns work / holds meetings, and you watch the company run via a real-time dashboard.

[中文](./README.zh-CN.md)

The authoritative architecture spec is [`ai-sim-company-架构设计.md`](./ai-sim-company-架构设计.md). This repo implements a locally-runnable simulation mode (non-containerized); see "Implementation status" below for deviations from the design doc.

## What it is

The user configures the business on `/setup` → the backend hot-reloads and re-seeds the CEO → the CEO decides autonomously (hire HR, assign tasks, hold meetings) based on the business description → HR hires engineers/designers → everyone thinks and collaborates on the simulation clock → the real-time dashboard shows capital / tasks / logs / agent details.

- **CEO makes real decisions**: each tick it thinks via the LLM and calls tools (`create_agent` / `send_message` / `create_task` / `call_meeting` …). The business description and budget are injected into its prompt.
- **LLM key configured once** (`.env` / `config/company.yaml`); agents never know which model serves them.
- **Local simulation mode**: `AGENT_BACKEND=simulated` — the Hub runs the agent main loop in-process (no Docker containers).

## Quick start (local, non-containerized)

Prereqs: Python 3.12+ (`python` on PATH), Node.js (`npm`), Redis on `localhost:6379` (password `123456`).

```bat
copy .env.example .env          :: fill in LLM_API_KEY (+ optional LLM_MODEL / LLM_BASE_URL)
start.bat                       :: start Redis (skipped if running) + backend :8000 + frontend :3000
```

Open http://localhost:3000/setup, configure the business → Apply → Console ▶ Play.

Scripts (Windows `.bat`):

| Script | Action |
|---|---|
| `start.bat` | Start Redis + backend (FastAPI :8000) + frontend (Next.js :3000), each in its own window |
| `stop.bat` | Kill backend/frontend by port + close launcher windows (Redis is left alone) |
| `reset.bat` | stop + clear Redis + SQLite + frontend `.next` cache → clean state |

## Configuration

- **`config/company.yaml`**: company business (name / business_description / initial_capital / monthly_budget) + CEO + LLM gateway + simulation params. `${VAR}` placeholders expand from env vars. The `company` section is hot-reloadable via `/setup` (POST /api/config); other sections are preserved.
- **`.env.example` → `.env`**: env vars (`LLM_API_KEY` required; `LLM_MODEL` / `LLM_BASE_URL` / `LLM_PROVIDER` optional). Auto-loaded by `aisim/__init__.py` (existing env vars take precedence). `.env` is gitignored.

LLM example (DeepSeek):

```
LLM_API_KEY=sk-...
LLM_MODEL=deepseek-v4-flash
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_PROVIDER=openai
```

## Frontend

Next.js 15 (App Router) + React 19 + Tailwind CSS 4 + Zustand + TanStack Query.

Routes:
- `/` Console: HUD (capital / burn / budget / agents / skills / mood) + TaskBoard + LogFeed (filter by kind + search, smart scroll) + AgentPanel + ControlBar (play/pause/speed/step/meeting/refresh)
- `/setup` Business config → hot-reload
- `/agents` Agent list + hire form (POST /api/agents)
- `/agents/[id]` Agent detail (role / status / skills / recent thoughts)
- `/dashboard` Company dashboard (org chart / cash flow / project board — placeholder)
- `/settings` LLM gateway config (routing / budget / usage, read-only)

Features: WebSocket exponential-backoff reconnect + status indicator, CSS Grid responsive layout, skeleton loading, toasts, pixel-art design tokens, a11y (aria / Esc to close modal).

## Backend

Python 3.12 + FastAPI + Redis (Pub/Sub + state) + SQLite (Hub state persistence) + Jinja2 prompt templates.

REST API (`/api`): `/state` `/config` `/agents` `/agents/{id}` `/simulation/control` `/llm/config` `/skills` `/tasks` `/meetings`. WebSocket `/ws` pushes frontend render events.

Agent simulation loop (`aisim/company/agent_runner.py`): each tick assembles a prompt (business description / budget / team / tasks / memory injected) → LLM multi-turn tool loop (ReAct) → tool results fed back. Role directives (`_directive`) enforce division of labor (CEO only hires HR; other hiring is HR's job).

## Project structure

```
ai-sim-company/
├── aisim/                # Python backend package
│   ├── shared/           # data models / channel names / config (config.py)
│   ├── company/          # Hub: hub / agent_manager / agent_runner / task_manager / profile_registry / org_chart
│   ├── agent/            # container-side agent (runtime / memory / identity)
│   ├── simulation/       # clock / economy / event_bus
│   ├── comm/             # message_bus / meeting
│   ├── skills/           # pool / sync / preset
│   ├── llm/              # gateway / router / provider / prompts/*.j2 (6 English templates)
│   ├── tools/            # create_agent / send_message / call_meeting / create_task / ...
│   ├── api/              # server / ws / routes / state
│   └── db.py             # SQLite persistence
├── frontend/             # Next.js frontend
│   └── src/
│       ├── app/          # page / layout / globals.css + dashboard/ settings/ agents/[id] setup/
│       ├── components/   # HUD / ControlBar / TaskBoard / AgentPanel / LogFeed / TopNav / MeetingDialog / ...
│       ├── hooks/        # useWebSocket / useGameEvents / useQueries
│       ├── store/        # useGameStore (Zustand) / useToastStore
│       ├── lib/          # config / query-client
│       └── types/        # game
├── config/company.yaml   # initial company config
├── .env.example          # env var template
├── start.bat / stop.bat / reset.bat   # one-click start/stop/reset (non-containerized)
├── docker-compose.yml / Dockerfile.company / Dockerfile.agent / Makefile  # containerized (design target)
├── tests/                # pytest (52 passed)
└── ai-sim-company-架构设计.md            # authoritative design doc
```

## Tests & dev

```bat
:: backend
pip install -r requirements-dev.txt
pytest                           :: 52 passed, 2 skipped (live LLM needs LLM_LIVE_TEST=1)
ruff check aisim tests
mypy aisim

:: frontend
cd frontend && npm install
npm run dev                      :: or npx tsc --noEmit for type check
```

## Implementation status vs design doc

The design doc is the authoritative spec; the current implementation is a local simulation mode with three deviations:

- **Agent backend**: design = each agent in its own Docker container (Hermes runtime); current local = `AGENT_BACKEND=simulated`, Hub runs the agent loop in-process. Docker mode (`docker-compose.yml` / `Dockerfile.agent`) is retained but not used in the local flow.
- **Frontend**: design = Phaser 3 pixel office; current = Phaser removed, replaced with a multi-route data dashboard.
- **Business setup**: added `/setup` page + `hub.apply_config` hot-reload (not in the design doc), letting users configure business + budget online.

## Conventions

- Communication over Redis Pub/Sub (`redis.asyncio`); channel naming in `aisim/shared/channels.py`.
- LLM API key only in `.env` / `config/company.yaml`; agents don't know the model; role→model routing in the LLM Gateway.
- Code identifiers, comments, and commit messages in English.
