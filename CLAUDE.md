# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project state

This project is **implemented and locally runnable** in a non-containerized simulation mode. The authoritative design spec is still `ai-sim-company-架构设计.md` (Chinese, ~49KB), but the current codebase has made three deliberate deviations from it (see "Implementation vs design" below). Treat the design doc as the long-term target; treat this file + the code as the current truth.

What exists and runs today:
- **Backend** (`aisim/`): FastAPI + Redis + SQLite, simulated agent runner, 6 role prompt templates, full REST + WebSocket API. `pytest`: 52 passed.
- **Frontend** (`frontend/`): Next.js 15 + React 19 + Tailwind 4 + Zustand + TanStack Query, multi-route data-dashboard (Phaser removed).
- **One-click launch**: `start.bat` / `stop.bat` / `reset.bat` (Windows) bring up Redis + backend (:8000) + frontend (:3000).
- **Business setup**: `/setup` page + `POST /api/config` hot-reloads the Hub with user-supplied business description + budget.

## What this project is

`ai-sim-company` is a **multi-agent AI company simulation platform**. The user configures the business (name/description/budget) on `/setup`; a CEO agent (LLM-driven) autonomously decides to hire and assign work; an HR Director agent designs/creates other agents; the company runs in real time, observed via a data dashboard.

- The user is a god-view observer and does **not** directly control agents.
- The CEO makes real decisions via an LLM; the HR Director creates agents; in local mode every agent runs as an in-process simulated loop inside the Hub (not separate Docker containers).
- Differentiator vs. the design doc's container target: the local dev path uses `AGENT_BACKEND=simulated` (Hub runs the agent tick loop directly). The Docker container path (`docker-compose.yml`, `Dockerfile.agent`) is retained but not used in the local flow.

## Implementation vs design (three deviations)

1. **Agent backend**: design = each agent in its own Docker container running Hermes runtime; **current = `simulated`** (Hub process runs the agent main loop, calling `LLMGateway.chat` directly). `aisim/company/agent_runner.py` is the simulated loop; `aisim/agent/` (runtime/memory/identity) is the container-side code kept for the Docker path.
2. **Frontend**: design = Phaser 3 pixel office; **current = removed Phaser**, replaced with a multi-route data dashboard (HUD / tasks / logs / agents / settings). No Phaser/EasyStar/Howler dependencies.
3. **Business setup**: design doc doesn't specify online config; **current = `/setup` page + `hub.apply_config` hot-reload** (stop -> clear Redis+SQLite -> reinit components -> start), injecting `business_description` + `monthly_budget` into the CEO's tick prompt.

## Core architectural principles (load-bearing - still respected where applicable)

1. **Agents are decoupled from the Hub's decision-making.** The Hub orchestrates; agents make decisions via LLM. In simulated mode the agent loop runs in the Hub process, but the boundary (Hub doesn't decide for agents) is preserved.
2. **Agent identity is runtime-defined, not baked into code.** Profile (role/personality/tools) comes from `ProfileRegistry`; in simulated mode it's registered directly rather than pushed over Redis, but the principle (no role hardcoded in agent code) holds.
3. **LLM API key is configured exactly once** (`.env` / `config/company.yaml`), agents never see it. Role->model routing happens in `LLMGateway`. ✓ implemented.
4. **Redis Pub/Sub is the only inter-agent / agent↔hub transport.** Channel naming in `aisim/shared/channels.py`. ✓ implemented (simulated agents still route messages through `MessageBus`).
5. **Two-layer Skill system**: Hermes-side learning (not in simulated mode) + Hub-side `SkillPool` (sharing/scoping/versioning/lifecycle). The Hub side is implemented (`aisim/skills/`); agent-side auto-extraction is a Docker-mode feature.
6. **File storage**: shared Docker volume in design; in local mode `tools/file_ops.py` is a stub. Keep file-tool logic behind an adapter for the future MinIO/S3 swap.
7. **Company Hub's boundary**: owns UI/simulation clock/economy/orchestration/profile-gen/LLM gateway/skill pool/message routing/file storage. Does **not** make agent decisions or manage agent memory. ✓ respected.

## Local dev topology

- **Redis** (fixed, `:6379`, password `123456`): message backbone + state + skill pool.
- **Company Hub** (`python -m uvicorn aisim.api.server:app --port 8000`): FastAPI + WebSocket + simulation + LLM gateway + simulated agent runner.
- **Frontend** (`cd frontend && npm run dev`, `:3000`): Next.js dev server.
- `start.bat` starts all three; `stop.bat` kills by port (8000/3000-3002); `reset.bat` clears Redis + SQLite + `.next`.

## Stack

- **Backend (Python 3.12)**: FastAPI, `redis.asyncio`, `httpx`, `jinja2` (prompts), `pydantic`, `sqlite3`. Package `aisim/`.
- **Frontend**: Next.js 15 (App Router) + React 19 + Tailwind CSS 4 + Zustand + TanStack Query. Lives in `frontend/`.
- **Infra (design target, not local)**: Docker Compose, Redis 7-alpine.

## Package layout (current)

`aisim/` organized by concern:
`company/` (hub, agent_manager, **agent_runner** [simulated loop], task_manager, profile_registry, org_chart) · `agent/` (runtime, memory, identity — container-side, unused in simulated) · `simulation/` (clock, economy, event_bus) · `comm/` (message_bus, meeting) · `skills/` (pool, sync, preset) · `llm/` (gateway, router, provider, `prompts/*.j2` — 6 English templates) · `tools/` (one file per agent tool) · `api/` (server, ws, routes, state) · `db.py` (SQLite) · `shared/` (models, channels, config).

`frontend/src/`:
`app/` (page, layout, globals.css + `dashboard/` `settings/` `agents/[id]` `setup/`) · `components/` (HUD, ControlBar, TaskBoard, AgentPanel, LogFeed, TopNav, MeetingDialog, QueryProvider, GameProvider, Toaster, Skeleton, ...) · `hooks/` (useWebSocket, useGameEvents, useQueries) · `store/` (useGameStore [Zustand], useToastStore) · `lib/` (config, query-client) · `types/` (game).

## Agent lifecycle & communication contract

Agent state machine: `booting -> initializing -> running -> offline` / `shutting down`. In simulated mode, agents skip the boot/register handshake (registered directly by `agent_runner`); in Docker mode the full handshake (subscribe `agent:{id}:profile`, publish `agent:register`, etc.) applies.

Four communication modes: **DM** (1:1), **Channel** (1:N), **Meeting** (N:N, LLM-hosted via `meeting.j2`), **Announcement** (1:All). Single `Message` schema. The Hub re-broadcasts renderable events to the frontend over WebSocket (`frontend:events`) with typed payloads (`agent_message`, `agent_action`, `agent_created`, `meeting_start`, `meeting_minutes`, `task_created`, `task_completed`, `state_snapshot`) — see `aisim/api/ws.py` and `frontend/src/types/game.ts` `FrontendEvent`.

## Tools & roles

Tools are assigned **per role** (see `TOOLS_BY_ROLE` in the design doc §四, and `aisim/tools/`). Notable: `create_agent` is granted to **both** CEO and HR Director. Senior engineers can `share_skill`; juniors can `learn_skill`. When adding a tool, update the role->tools mapping and confirm the hub's tool dispatcher (`agent_runner._execute_tool`) knows it.

## Commands

```bat
copy .env.example .env          :: fill LLM_API_KEY (+ optional LLM_MODEL/BASE_URL)
start.bat                       :: Redis + backend :8000 + frontend :3000
stop.bat                        :: kill backend/frontend by port
reset.bat                       :: stop + clear Redis + SQLite + .next
```

```bat
:: dev / tests
pytest                          :: 52 passed, 2 skipped (live LLM needs LLM_LIVE_TEST=1)
ruff check aisim tests
mypy aisim
cd frontend && npm run dev
cd frontend && npx tsc --noEmit :: type check
```

Config files: `config/company.yaml` (business + CEO + LLM + simulation; `company` section hot-reloadable via `/setup`), `.env` (env vars, auto-loaded by `aisim/__init__.py`).

## Working in this repo

- The design doc `ai-sim-company-架构设计.md` is the authoritative long-term spec; this file reflects current implementation. When the two disagree, the code is truth for local mode, the doc is truth for the container target.
- Code, identifiers, comments, and commit messages are **English**.
- Before changing agent behavior, read `agent_runner._build_prompt` / `_directive` (role-specific guidance + business/budget injection) and the relevant `aisim/llm/prompts/*.j2`.
- The LLM API key never goes in the frontend or agent-visible config. Configure via `.env` / `config/company.yaml`.
