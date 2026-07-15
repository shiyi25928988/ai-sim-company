# ai-sim-company

> 多智能体 AI 公司模拟平台 — CEO 一人创立 → 自主招人 → 像素风办公室里自动运转。

详细架构设计见 [`ai-sim-company-架构设计.md`](./ai-sim-company-架构设计.md)（权威设计文档）。
本仓库目前处于**骨架阶段**：目录结构、Docker 编排、Python 包与前端脚手架已就位，
各模块为带签名与文档字符串的桩代码，待按 MVP 路线图逐步实现。

## 架构一句话

用户配置初始条件 → CEO（LLM 驱动）自主决策招人 → HR Director 落地创建 Agent →
每个 Agent 独立 Docker 容器运行 → Redis Pub/Sub 通信 → Phaser 3 像素风办公室实时上演。

- **两个固定容器**：`redis`（消息骨干 + 状态 + Skill Pool）、`company`（Company Hub）。
- **N 个动态容器**：`agent:*`，由 Company Hub 通过 Docker API 创建/销毁。
- **Agent 身份 100% 由启动参数定义**：容器只认 `REDIS_URL` 与 `AGENT_ID`，Profile 由 Hub 在上线时下发。
- **LLM API Key 只在 Company Hub 配一次**，Agent 不感知自己用什么模型。

## 目录结构

```
ai-sim-company/
├── aisim/                # Python 后端包 (Company Hub + Agent Runtime + 仿真 + 通信 + Skills + LLM + Tools + API)
│   ├── shared/           # Hub 与 Agent 共享的数据模型 / 通道名 / 配置
│   ├── company/          # Company Hub: hub / agent_manager / profile_registry / org_chart
│   ├── agent/            # Agent 容器内运行: runtime / memory / identity
│   ├── simulation/       # 仿真引擎: clock / economy / event_bus
│   ├── comm/             # 通信: message_bus / meeting
│   ├── skills/           # Skill 管理: pool / sync / preset
│   ├── llm/              # LLM 网关: gateway / router / prompts/*.j2
│   ├── tools/            # Agent 工具: create_agent / send_message / ...
│   ├── api/              # FastAPI + WebSocket: server / ws / routes
│   └── db.py             # SQLite 持久化
├── frontend/             # Next.js + React 19 + Phaser 3 像素风前端
├── config/company.yaml   # 公司初始配置 (CEO + 资金 + LLM 路由)
├── Dockerfile.company    # Company Hub 镜像
├── Dockerfile.agent      # Agent 基础镜像 (不含身份)
├── docker-compose.yml    # redis + company + frontend + agent:ceo
├── Makefile              # 常用命令
└── tests/                # 测试
```

## 快速开始 (待实现)

```bash
cp .env.example .env        # 填入 LLM_API_KEY
docker compose up           # 启动 redis + company + frontend + ceo
# 前端:  http://localhost:3000   (像素风办公室)
# API/WS: http://localhost:8000
```

本地开发：

```bash
# 后端
pip install -r requirements-dev.txt
ruff check aisim tests
mypy aisim
pytest

# 前端
cd frontend && npm install && npm run dev
```

## 实现约定

- Agent 镜像复制**整个** `aisim/` 包并以 `python -m aisim.agent.runtime` 启动，
  使 Hub 与 Agent 内部导入统一为 `aisim.*`（身份仍仅由 `REDIS_URL`+`AGENT_ID` 定义；
  与设计文档中“仅复制 agent/+shared/”的精简写法有所偏差，理由是导入一致性）。
- 通信统一走 Redis Pub/Sub（`redis.asyncio`），通道命名见 `aisim/shared/channels.py`。
- 设计文档为中文；标识符用英文，注释沿用中文。
