# ai-sim-company

> 多智能体 AI 公司模拟平台 -- 配置业务与预算，CEO（LLM 驱动）自主招聘/派活/开会，实时看板观察公司运转。

[English](./README.md)

详细架构设计见 [`ai-sim-company-架构设计.md`](./ai-sim-company-架构设计.md)（权威设计文档）。本仓库已实现本地可跑的仿真模式（非容器化），与设计文档的容器化目标在 Agent 后端上有差异（见下文「实现状态」）。

## 是什么

用户在 `/setup` 页配置公司业务（业务描述、初始资金、月预算）-> 后端热重载并重新 seed CEO -> CEO 据业务描述自主决策（招 HR、派任务、开会）-> HR 落地招聘工程师/设计师 -> 全员在仿真时钟里思考、协作、产出 -> 前端实时看板展示资金/任务/日志/Agent 详情。

- **CEO 真做决策**：每 tick 用 LLM 思考 + 调工具（create_agent / send_message / create_task / call_meeting ...），业务描述与预算注入其 prompt。
- **LLM Key 只配一次**：在 `.env` / `config/company.yaml` 配置，Agent 不感知模型。
- **本地仿真模式**：`AGENT_BACKEND=simulated`，Hub 进程内跑 Agent 主循环（无需 Docker 容器）。

## 快速开始（本地，非容器化）

前置：Python 3.12+（`python` 在 PATH）、Node.js（`npm`）、Redis 在 `localhost:6379`（密码 `123456`）。

```bat
copy .env.example .env          :: 填入 LLM_API_KEY（及可选的 LLM_MODEL / LLM_BASE_URL）
start.bat                       :: 启动 Redis(已跑则跳过) + 后端 :8000 + 前端 :3000
```

打开 http://localhost:3000/setup 配置业务 -> Apply -> 主控台点 ▶ Play。

脚本（Windows `.bat`）：

| 脚本 | 作用 |
|---|---|
| `start.bat` | 启动 Redis + 后端(FastAPI :8000) + 前端(Next.js :3000)，各在独立窗口 |
| `stop.bat` | 按端口杀后端/前端进程 + 关启动器窗口（Redis 保留） |
| `reset.bat` | 先 stop，再清 Redis + SQLite + 前端 .next 缓存，回到干净状态 |

## 配置

- **`config/company.yaml`**：公司业务（name / business_description / initial_capital / monthly_budget）+ CEO + LLM 网关 + 仿真参数。`${VAR}` 占位符从环境变量展开。`company` 段可由 `/setup` 页（POST /api/config）热重载，其他段保留。
- **`.env.example` -> `.env`**：环境变量（`LLM_API_KEY` 必需；`LLM_MODEL` / `LLM_BASE_URL` / `LLM_PROVIDER` 等可选）。`aisim/__init__.py` 启动时自动加载 `.env`（已有环境变量优先）。`.env` 被 gitignore。

LLM 示例（DeepSeek）：

```
LLM_API_KEY=sk-...
LLM_MODEL=deepseek-v4-flash
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_PROVIDER=openai
```

## 前端

Next.js 15 (App Router) + React 19 + Tailwind CSS 4 + Zustand + TanStack Query。

路由：
- `/` 主控台：HUD（资金/烧钱/预算/Agent/技能/情绪）+ TaskBoard + LogFeed（按类型过滤+搜索，智能滚动）+ AgentPanel + ControlBar（播放/暂停/倍速/单步/开会/刷新）
- `/setup` 业务配置：公司名 / 业务描述 / 初始资金 / 月预算 -> 热重载
- `/agents` Agent 列表 + 雇佣表单（POST /api/agents）
- `/agents/[id]` Agent 详情（角色/状态/技能/近期思考）
- `/dashboard` 公司仪表盘（org chart / cash flow / project board - 占位）
- `/settings` LLM 网关配置（路由表/预算/用量，只读）

特性：WS 指数退避重连 + 连接状态指示、CSS Grid 响应式布局、骨架屏、toast、pixel 风格 design token、a11y（aria / Esc 关闭模态）。

## 后端

Python 3.12 + FastAPI + Redis（Pub/Sub + 状态）+ SQLite（Hub 状态持久化）+ Jinja2 prompt 模板。

REST API（`/api`）：`/state` `/config` `/agents` `/agents/{id}` `/simulation/control` `/llm/config` `/skills` `/tasks` `/meetings`。WebSocket `/ws` 推前端渲染事件。

Agent 仿真主循环（`aisim/company/agent_runner.py`）：每 tick 组装 prompt（注入业务描述/预算/团队/任务/记忆）-> LLM 多轮工具循环（ReAct）-> 工具结果回填。角色指令（`_directive`）强制分工（CEO 只招 HR，其余招聘归 HR）。

## 项目结构

```
ai-sim-company/
├── aisim/                # Python 后端包
│   ├── shared/           # 数据模型 / 通道名 / 配置 (config.py)
│   ├── company/          # Hub: hub / agent_manager / agent_runner / task_manager / profile_registry / org_chart
│   ├── agent/            # Agent 容器内运行 (runtime / memory / identity)
│   ├── simulation/       # clock / economy / event_bus
│   ├── comm/             # message_bus / meeting
│   ├── skills/           # pool / sync / preset
│   ├── llm/              # gateway / router / provider / prompts/*.j2 (6 个英文模板)
│   ├── tools/            # create_agent / send_message / call_meeting / create_task / ...
│   ├── api/              # server / ws / routes / state
│   └── db.py             # SQLite 持久化
├── frontend/             # Next.js 前端
│   └── src/
│       ├── app/          # page / layout / globals.css + dashboard/ settings/ agents/[id] setup/
│       ├── components/   # HUD / ControlBar / TaskBoard / AgentPanel / LogFeed / TopNav / MeetingDialog / ...
│       ├── hooks/        # useWebSocket / useGameEvents / useQueries
│       ├── store/        # useGameStore (Zustand) / useToastStore
│       ├── lib/          # config / query-client
│       └── types/        # game
├── config/company.yaml   # 公司初始配置
├── .env.example          # 环境变量模板
├── start.bat / stop.bat / reset.bat   # 一键启停重置（非容器化）
├── docker-compose.yml / Dockerfile.company / Dockerfile.agent / Makefile  # 容器化（设计目标）
├── tests/                # pytest（52 passed）
└── ai-sim-company-架构设计.md            # 权威设计文档
```

## 测试与开发

```bat
:: 后端
pip install -r requirements-dev.txt
pytest                           :: 52 passed, 2 skipped (live LLM)
ruff check aisim tests
mypy aisim

:: 前端
cd frontend && npm install
npm run dev                      :: 或 npx tsc --noEmit 类型检查
```

## 实现状态与设计文档的差异

设计文档（`ai-sim-company-架构设计.md`）是权威 spec，当前实现为本地仿真模式，有以下调整：

- **Agent 后端**：设计为每个 Agent 独立 Docker 容器（Hermes runtime）；当前本地用 `AGENT_BACKEND=simulated`，Hub 进程内跑 Agent 主循环（直接调 LLM Gateway）。Docker 模式（`docker-compose.yml` / `Dockerfile.agent`）保留但未在本地流程使用。
- **前端**：设计为 Phaser 3 像素风办公室；当前已移除 Phaser，改为多路由数据看板（HUD/任务/日志/Agent 详情）。
- **业务配置**：新增 `/setup` 页 + `hub.apply_config` 热重载（设计文档未明确），让用户在线配置业务与预算。

## 实现约定

- 通信统一走 Redis Pub/Sub（`redis.asyncio`），通道命名见 `aisim/shared/channels.py`。
- LLM API Key 只在 `.env` / `config/company.yaml` 配置，Agent 不感知模型；role->model 路由在 LLM Gateway。
- 代码标识符用英文，注释为英文（设计文档为中文）。
