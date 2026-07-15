# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project state

This is a **greenfield project at the design stage**. The repository currently contains a single document — `ai-sim-company-架构设计.md` (in Chinese, ~49KB) — and no code, build system, dependencies, or tests have been written yet. There are no git commits.

Treat `ai-sim-company-架构设计.md` as the authoritative spec. When asked to implement anything, read that document first; the sections below summarize the decisions that constrain implementation but are not a substitute for it.

## What this project is

`ai-sim-company` is a **multi-agent AI company simulation platform**. The user configures initial conditions; a CEO agent (founded alone, LLM-driven) autonomously decides to hire; an HR Director agent designs candidate profiles and creates new agents; the company grows and runs in real time, visualized as a pixel-art office.

- The user is a god-view observer and does **not** directly control agents.
- The CEO makes real decisions via an LLM; the HR Director creates agents; **every agent runs in its own Docker container**.
- Differentiator vs. prior work: agents are dynamically created Docker containers (not config-file / in-process), the CEO/HR do the creating, and the underlying agent runtime is **Hermes Agent (Nous Research)**.

## Core architectural principles (non-obvious — must be respected)

These are the load-bearing decisions in the design doc. Violating any of them changes the nature of the project:

1. **Each agent is a separate Docker container** running its own Hermes runtime — never in-process threads or tasks of the hub.
2. **The base agent image carries no identity.** Identity is 100% defined by two startup env vars only: `REDIS_URL` and `AGENT_ID`. No role/personality/system-prompt is baked into the image.
3. **The Agent Profile is pushed at runtime by Company Hub** over Redis (`agent:{id}:profile`) when the agent boots and reports in. The container does not know who it is until the hub tells it.
4. **The LLM API key is configured exactly once, in Company Hub.** Agents never see a key and never know which model serves them. All LLM calls are proxied through the hub gateway; role→model routing happens there (e.g. `ceo`→`gpt-4o`, `senior-engineer`→`gpt-4o-mini`), with a daily token budget and automatic fallback to the cheapest model when exceeded.
5. **Redis Pub/Sub is the only inter-agent / agent↔hub transport.** No direct HTTP/RPC between agents. Channels follow a fixed naming convention (see the doc's "通信系统" section for the full table).
6. **Two-layer Skill system with a strict split of responsibility:** Hermes (inside the agent container) **learns** — auto-extracts experience into skills, self-improves on feedback, FTS5 search, `agentskills.io`-compatible. The Company Skill Pool (in the hub, Redis-backed) **manages** — sharing, distribution, permission scoping (`company`/`department`/`role`/`personal` levels), versioning, and the `draft→published→deprecated→archived` lifecycle.
7. **File storage is a shared Docker Volume** for MVP (`/workspace/shared` mounted by all agents, plus per-agent `/workspace/{agent_id}`). The design explicitly calls for a single adapter swap to MinIO/S3 later — keep file-tool logic behind an adapter so this stays a one-place change.
8. **Company Hub's boundary:** it owns UI, the simulation clock, the economy, container orchestration, profile generation, the LLM gateway, the skill pool, message routing, and file storage. It does **not** make agent decisions, run agent code, or manage agent memory — those belong to the agent container.

## Container topology

- **Two fixed containers** (defined in `docker-compose.yml`): `redis` (message backbone + state + skill pool) and `company` (Company Hub: FastAPI + Phaser UI + simulation + Docker-API orchestration + LLM gateway).
- **N dynamic `agent:*` containers**, created/destroyed at runtime by Company Hub via the Docker API. The CEO agent is the one fixed agent (present at company founding); all others (HR, engineers, designer, …) are created dynamically by CEO/HR.
- All containers share the `aisim-net` Docker network. The hub mounts `/var/run/docker.sock` so it can spawn agent containers.

## Intended stack

- **Backend (Python 3.12):** FastAPI (`aisim/api/`), `aioredis`/`redis`, `httpx`, Hermes Agent runtime. Python package is `aisim/`.
- **Frontend:** Next.js + React 19, **Phaser 3** (pixel office rendering + sprite animation state machine), **EasyStar.js** (A* pathfinding), Tailwind CSS 4, Howler.js (audio). Lives in `frontend/`.
- **Infra:** Docker Compose, Redis 7-alpine.

## Intended package layout (from the design doc)

The `aisim/` Python package is organized by concern, not by layer:
`company/` (hub, agent_manager, profile_registry, org_chart) · `agent/` (runtime entrypoint, memory, identity — runs **inside** the agent container) · `simulation/` (clock, economy, event_bus) · `comm/` (message_bus, meeting) · `skills/` (pool, sync, preset) · `llm/` (gateway, router, `prompts/*.j2` per role) · `tools/` (one file per agent tool, e.g. `create_agent.py`) · `api/` (FastAPI server, ws, routes) · `db.py` (SQLite persistence).

Note the split: `aisim/company/*` runs in the hub; `aisim/agent/*` runs inside each agent container. Both are copied into the respective Dockerfiles (`Dockerfile.company`, `Dockerfile.agent`), and `aisim/shared/` is shared between them.

## Agent lifecycle & communication contract

Agent state machine: `booting → initializing → running → offline` / `shutting down`. Boot sequence (agent side): connect Redis → publish `agent:register` → subscribe `agent:{id}:profile` → receive Profile → init Hermes Runtime → subscribe `simulation:tick` + `agent:{id}:inbox` → publish `agent:ready` → enter tick loop. Heartbeat is 5s; the hub marks an agent offline after a 15s heartbeat timeout.

Four communication modes: **DM** (1:1), **Channel** (1:N), **Meeting** (N:N, LLM-hosted), **Announcement** (1:All). Messages use a single `Message` schema with `type`/`sender`/`recipients`/`channel`/`content`/`content_type`/`priority`. The hub re-broadcasts renderable events to the frontend over WebSocket (`frontend:events`) with typed payloads (`agent_message`, `agent_action`, `agent_created`, `meeting_start`, `state_snapshot`).

## Tools & roles

Tools are assigned **per role** (see `TOOLS_BY_ROLE` in the design doc, §四). Notable: `create_agent` is granted to **both** CEO and HR Director (either can spawn agents). Senior engineers can `share_skill` to juniors; juniors can `learn_skill` from the company pool. When adding a tool, update the role→tools mapping and confirm the hub's tool dispatcher knows it.

## Intended commands (not yet implemented)

The design doc specifies these, but neither `docker-compose.yml` nor `Makefile` exist yet. Once created, they should match:
- `docker compose up` — start redis + company + ceo (the design's "single-line launch").
- Web UI at `http://localhost:3000`, WebSocket on `:8000`.
- `LLM_API_KEY` must be set in the environment before `docker compose up`.
- Makefile targets: `up`, `down`, `logs`, `logs-ceo`, `reset` (`down -v` + remove `data/`), `agent NAME=...` (manual debug-only agent spawn).

## Working in this repo

- Before writing code, re-read the relevant section of `ai-sim-company-架构设计.md` — it contains concrete schemas (`AgentProfile`, `Skill`, `Message`), the full Redis channel table, the WebSocket protocol payloads, and the complete `docker-compose.yml` / `Makefile` / `Dockerfile.*` source as designed. Implement to those, don't re-derive them.
- The design doc is in Chinese; code, identifiers, and commit messages should follow the conventions shown there (English identifiers, Chinese comments are acceptable where the doc uses them).
- The MVP roadmap (§十四) phases the work: Phase 1 = infra + agent runtime + CEO `create_agent`; Phase 2 = pixel frontend; Phase 3 = economy/org/skills/meetings; Phase 4 = polish. Match the current phase when scoping changes.
