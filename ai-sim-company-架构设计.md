# 🏢 ai-sim-company 最终架构设计

> 多智能体 AI 公司模拟平台  
> CEO 一人创立 → 自主招人 → 像素风办公室里自动运转

---

## 目录

1. [项目定位](#一项目定位)
2. [整体架构](#二整体架构)
3. [Company Hub](#三company-hub)
4. [Agent 模型与生命周期](#四agent-模型与生命周期)
5. [Agent 容器方案](#五agent-容器方案)
6. [通信系统 (Redis)](#六通信系统-redis)
7. [LLM 统一网关](#七llm-统一网关)
8. [Skill 管理体系](#八skill-管理体系)
9. [文件存储](#九文件存储)
10. [前端 (像素风办公室)](#十前端-像素风办公室)
11. [部署方案](#十一部署方案)
12. [启动流程](#十二启动流程)
13. [项目结构](#十三项目结构)
14. [MVP 路线图](#十四mvp-路线图)

---

## 一、项目定位

### 核心玩法

```
用户配置公司初始条件 → CEO 孤身一人 → 自主决策招人 → 公司逐渐壮大 → 像素风办公室实时上演
```

- **用户是上帝视角**，不直接操控 Agent
- **CEO 是真正做决策的人**，通过 LLM 自主判断
- **HR Director 负责落地**，设计候选人画像并创建 Agent
- **所有 Agent 都有独立的容器运行时**

### 竞品差异

| | 现有项目 | ai-sim-company |
|---|---|---|
| Agent 创建 | 配置文件写死 | **CEO/HR 动态创建 Docker 容器** |
| Agent 运行时 | 同进程线程 | **独立 Docker 容器** |
| 底层引擎 | 自研 | **Hermes Agent (Nous Research)** |
| LLM | 全局一个 Key | **Company Hub 统一网关** |
| 前端 | 终端/简单 UI | **Phaser 3 像素风办公室** |
| Skill | 无或简单 | **Hermes + 公司池双层体系** |

---

## 二、整体架构

```
┌──────────────────────────────────────────────────────────────────┐
│                        Docker Network: aisim-net                  │
│                                                                  │
│  ┌──────────┐                                                    │
│  │  Redis   │  ←── 消息骨干 (Pub/Sub) + 状态存储 + Skill Pool    │
│  │  :6379   │                                                    │
│  └────┬─────┘                                                    │
│       │                                                          │
│  ┌────┴──────────────────────────────────────────────────────┐   │
│  │                   Company Hub :8000 (WebSocket)            │   │
│  │                                                           │   │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌────────────┐  │   │
│  │  │ Web UI  │  │ 仿真引擎 │  │ Agent管理│  │ LLM Gateway│  │   │
│  │  │ Phaser3 │  │ Tick时钟│  │ 容器编排 │  │ 统一API Key│  │   │
│  │  │ :3000   │  │ 经济系统│  │ 生命周期 │  │ 路由分级   │  │   │
│  │  └─────────┘  └─────────┘  └─────────┘  └────────────┘  │   │
│  │                                                           │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │   │
│  │  │ Skill Pool   │  │ Message Bus  │  │  File Storage │   │   │
│  │  │ 公司知识资产  │  │ 消息路由分发  │  │ 共享 Volume   │   │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘   │   │
│  └──────────────────────────┬───────────────────────────────┘   │
│                             │                                   │
│     ┌───────────────────────┼───────────────────────┐           │
│     │                       │                       │           │
│  ┌──┴──────────┐   ┌───────┴───────┐   ┌───────────┴───────┐   │
│  │ agent:ceo   │   │ agent:hr      │   │ agent:eng-jordan  │   │
│  │ (固定)       │   │ (CEO 创建)    │   │ (HR 创建)         │   │
│  │             │   │              │   │                   │   │
│  │ Hermes      │   │ Hermes       │   │ Hermes            │   │
│  │ Runtime     │   │ Runtime      │   │ Runtime           │   │
│  └─────────────┘   └──────────────┘   └───────────────────┘   │
│                                                                  │
│     docker run ... (Company Hub 动态创建/销毁)                    │
│                                                                  │
│     ┌──────────┐  ┌──────────┐  ┌──────────┐                   │
│     │agent:    │  │agent:    │  │agent:    │  ...              │
│     │eng-sam   │  │designer  │  │sales     │                   │
│     └──────────┘  └──────────┘  └──────────┘                   │
└──────────────────────────────────────────────────────────────────┘
```

### 两个固定容器 + N 个动态容器

| 容器 | 数量 | 说明 |
|------|------|------|
| `redis` | 1 | 消息骨干 + 状态存储 + Skill Pool |
| `company-hub` | 1 | 前端 + 后端 + 仿真引擎 + LLM + Agent 编排 |
| `agent:*` | N | 每个 Agent 一个独立容器，CEO 固定存在，其余动态创建 |

---

## 三、Company Hub

### 职责边界

Company Hub 是系统的"大脑"，所有 Agent 都通过它间接交互。

```
Company Hub 负责:
  ✅ Web UI (Phaser 3 像素风前端，端口 3000)
  ✅ WebSocket Server (前端实时通信，端口 8000)
  ✅ 仿真时钟 (统一的 Tick 信号广播)
  ✅ 经济系统 (收支、薪资、融资、破产判定)
  ✅ Agent 容器编排 (通过 Docker API 创建/停止/删除)
  ✅ Agent 身份 Profile 生成与管理
  ✅ LLM 统一网关 (API Key 只在这里配一次)
  ✅ Skill Pool 管理 (公司级知识资产)
  ✅ 消息路由 (DM / Channel / Meeting / Announcement)
  ✅ 文件存储管理 (共享 Volume)

Company Hub 不做:
  ❌ Agent 的具体决策 (那是 Agent 自己的事)
  ❌ 代码执行 (Agent 容器自己有沙箱)
  ❌ Agent 的个人记忆管理 (Agent 容器自己维护)
```

### 核心组件

```python
# Company Hub 的主结构

class CompanyHub:
    """
    Company App — 系统的中枢。
    前端 (Phaser) + 后端 (FastAPI) 一体。
    """

    # ═══ 前端 ═══
    web_ui: PhaserOfficeApp         # 像素风办公室 (端口 3000)
    ws_server: WebSocketServer      # 前端实时通信 (端口 8000)

    # ═══ 仿真 ═══
    clock: SimulationClock          # Tick 时钟，控制时间流速
    economy: EconomyEngine          # 财务模拟
    event_bus: EventBus             # 市场事件、随机事件

    # ═══ Agent 管理 ═══
    agent_manager: AgentManager     # 容器编排 (Docker API)
    profile_registry: ProfileRegistry  # Agent 身份存储

    # ═══ LLM ═══
    llm_gateway: LLMGateway         # 统一 LLM 接入

    # ═══ 知识 ═══
    skill_pool: SkillPool           # 公司级 Skill 管理

    # ═══ 通信 ═══
    message_bus: MessageBus         # Redis Pub/Sub 消息路由
```

---

## 四、Agent 模型与生命周期

### Agent = 身份 Prompt + 记忆 + 工具权限

Agent 不携带 LLM 配置。LLM 调用全部走 Company Hub 的网关。

```python
@dataclass
class AgentProfile:
    """Agent 的完整身份 — 由 Company Hub 下发"""
    agent_id: str               # "eng-jordan"
    name: str                   # "Jordan"
    role: str                   # "Senior Engineer"
    department: str             # "Engineering"

    # ═══ 人格 ═══
    personality: Personality    # Big-5: O, C, E, A, N

    # ═══ 职责 ═══
    responsibilities: list[str]
    report_to: str              # 汇报给谁 (agent_id)
    salary: int

    # ═══ 能力 ═══
    system_prompt: str          # 这一 Tick 的完整 System Prompt
    tools: list[str]            # 根据角色分配的可用工具
    skills: list[str]           # 继承的 Skill ID 列表

    # ═══ 状态 ═══
    mood: float                 # -1.0 ~ 1.0
    energy: float               # 0 ~ 100
    status: str                 # booting | ready | working | offline

    # ═══ 资源 ═══
    workspace: str              # /workspace/eng-jordan
```

### Agent 创建 → 运行 → 销毁

```
        ┌─────────┐
        │ 不存在   │
        └────┬────┘
             │ CEO/HR 调用 create_agent 工具
             │ → Company Hub 通过 Docker API 启动容器
             ▼
   ┌─────────────────┐
   │ BOOTING          │  容器启动，连接 Redis，发报到消息
   └────────┬────────┘
            │ Hub 收到 agent:register → 下发 Profile
            ▼
   ┌─────────────────┐
   │ INITIALIZING     │  加载 Hermes Runtime + Memory + Skills
   └────────┬────────┘
            │ 发 agent:ready
            ▼
   ┌─────────────────────────────────────────────────┐
   │ RUNNING                                          │
   │                                                 │
   │ 每 Tick:                                        │
   │  ← Redis 收 simulation:tick                     │
   │  → 检查 inbox                                   │
   │  → Hermes.decide() — 走 Hub LLM Gateway         │
   │  → Hermes.execute() — 调用工具                   │
   │  → 汇报结果给 Hub                                │
   │  → 同步 Skills 到公司池                          │
   │  → 心跳 5s/次                                    │
   └────────┬────────────┬───────────────────────────┘
            │            │
     心跳超时 15s    CEO/HR 调用 remove_agent
            │            │ (或公司破产)
            ▼            ▼
   ┌─────────────┐  ┌──────────────┐
   │ OFFLINE     │  │ SHUTTING     │
   │ 等待恢复     │  │ DOWN         │
   └─────────────┘  └──────┬───────┘
                           │ docker rm
                           ▼
                      ┌─────────┐
                      │ 不存在   │
                      └─────────┘
```

### 角色与工具对照表

```python
TOOLS_BY_ROLE = {
    "ceo": [
        "create_agent",
        "send_message",
        "call_meeting",
        "web_search",
        "view_finance",
        "set_strategy",
        "approve_budget",
    ],
    "hr-director": [
        "create_agent",         # HR 也能创建 Agent
        "send_message",
        "call_meeting",
        "view_team",
        "schedule_interview",
        "onboard_agent",
        "share_skill",
    ],
    "senior-engineer": [
        "write_code",
        "run_tests",
        "git_commit",
        "send_message",
        "code_review",
        "web_search",
        "write_file",
        "read_file",
        "share_skill",          # 可以把经验传给 Junior
    ],
    "junior-engineer": [
        "write_code",
        "run_tests",
        "send_message",
        "ask_for_help",
        "learn_skill",          # 可以主动学习
        "write_file",
        "read_file",
    ],
    "designer": [
        "create_design",
        "export_asset",
        "send_message",
        "web_search",
        "write_file",
        "read_file",
    ],
}
```

---

## 五、Agent 容器方案

### 设计原则

> **基础镜像不含身份，身份 100% 由启动参数定义。**

```dockerfile
# Dockerfile.agent — Agent 基础镜像

FROM python:3.12-slim

LABEL org.aisim.role="agent-base"

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl ca-certificates git \
    && rm -rf /var/lib/apt/lists/*

# Hermes Agent + 依赖
RUN pip install --no-cache-dir \
    hermes-agent \
    redis[hiredis] \
    httpx

# Agent 运行时代码
COPY aisim/agent/ /app/agent/
COPY aisim/shared/ /app/shared/

WORKDIR /app

# ★ 启动参数只有两个环境变量
ENTRYPOINT ["python", "-m", "agent.runtime"]
```

### Agent 容器启动方式

```bash
# CEO (公司创立时就存在，写在 docker-compose.yml 中)
docker run -d \
  --name aisim-agent-ceo \
  --network aisim-net \
  --restart unless-stopped \
  -e REDIS_URL=redis://redis:6379 \
  -e AGENT_ID=ceo-alex \
  -v agent_ceo_workspace:/workspace/ceo-alex \
  -v company_files:/workspace/shared \
  aisim-agent:latest

# HR Director (CEO 动态创建)
docker run -d \
  --name aisim-agent-hr-taylor \
  --network aisim-net \
  --restart unless-stopped \
  -e REDIS_URL=redis://redis:6379 \
  -e AGENT_ID=hr-taylor \
  -v agent_hr_workspace:/workspace/hr-taylor \
  -v company_files:/workspace/shared \
  aisim-agent:latest

# Engineer (HR 动态创建)
docker run -d \
  --name aisim-agent-eng-jordan \
  --network aisim-net \
  --restart unless-stopped \
  -e REDIS_URL=redis://redis:6379 \
  -e AGENT_ID=eng-jordan \
  -v agent_eng_jordan_workspace:/workspace/eng-jordan \
  -v company_files:/workspace/shared \
  --memory="256m" \
  --cpus="0.5" \
  aisim-agent:latest
```

### 只有两个启动参数

| 环境变量 | 含义 | 示例 |
|----------|------|------|
| `REDIS_URL` | Redis 连接地址 (所有 Agent 统一) | `redis://redis:6379` |
| `AGENT_ID` | Agent 唯一身份证号 | `eng-jordan` |

**身份 Profile 由 Company Hub 在 Agent 容器上线时动态下发。**

### Agent 启动注册流程

```
Agent 容器启动
     │
     ▼
1. 连接 Redis
     │
     ▼
2. PUB agent:register {"agent_id": "eng-jordan"}  → Hub
     │
     ▼
3. SUB agent:eng-jordan:profile  ← Hub 下发完整身份
     │
     ▼
4. 初始化 Hermes Runtime (profile.system_prompt + tools + skills + memory)
     │
     ▼
5. PUB agent:ready
     │
     ▼
6. 进入主循环:
   SUB simulation:tick        ← 等待时钟信号
   SUB agent:eng-jordan:inbox ← 等待消息
   → Hermes.decide()         ← 走 Hub LLM Gateway
   → 执行动作
   → 汇报 + 心跳
```

### Agent Runtime 主循环

```python
# aisim/agent/runtime.py

import os, json, time, asyncio
import aioredis
from hermes import HermesRuntime
from agent.memory import MemoryManager

async def main():
    agent_id = os.environ["AGENT_ID"]
    redis_url = os.environ["REDIS_URL"]
    redis = await aioredis.from_url(redis_url)
    pubsub = redis.pubsub()

    # ── 报到 ──
    await redis.publish("agent:register", json.dumps({
        "agent_id": agent_id, "status": "booting"
    }))

    # ── 等待 Profile ──
    await pubsub.subscribe(f"agent:{agent_id}:profile")
    profile = await wait_for_message(pubsub)

    # ── 初始化 ──
    runtime = HermesRuntime(
        profile=profile,
        tools=profile["tools"],
        memory=MemoryManager(agent_id),
    )

    # ── 订阅信号 ──
    await pubsub.subscribe("simulation:tick")
    await pubsub.subscribe(f"agent:{agent_id}:inbox")

    # ── 就绪 ──
    await redis.publish("agent:ready", agent_id)

    # ── 主循环 ──
    async for msg in pubsub.listen():
        if msg["channel"] == b"simulation:tick":
            await handle_tick(runtime, redis, agent_id)
        elif msg["channel"] == f"agent:{agent_id}:inbox".encode():
            await handle_message(runtime, json.loads(msg["data"]))

    # ── 关闭 ──
    await redis.publish("agent:offline", agent_id)
```

---

## 六、通信系统 (Redis)

### Redis 通道设计

```
通道                       方向              说明
───────────────────────────────────────────────────────────
simulation:tick            Hub → All Agents   仿真时钟信号 (每 Tick 广播)
agent:{id}:inbox           Hub → Agent        Agent 专属收件箱
agent:{id}:profile         Hub → Agent        Agent 身份 Profile 下发
agent:{id}:skills:init     Hub → Agent        入职时 Skill 初始化
agent:{id}:skills:pending  Hub → Agent        待学习的 Skill
agent:{id}:heartbeat       Agent → Hub        心跳 (5s/次)

agent:register             Agent → Hub        报到
agent:ready                Agent → Hub        就绪
agent:offline              Agent → Hub        离线
hub:action                 Agent → Hub        动作汇报
hub:skill:new              Agent → Hub        新 Skill 上报

frontend:events            Hub → 前端 WS      前端渲染事件
```

### 消息格式

```python
@dataclass
class Message:
    """Agent 间通信的统一格式"""
    id: str
    type: str                   # dm | channel | meeting | announcement
    sender: str                 # agent_id
    recipients: list[str]       # 目标 agent_id 列表
    channel: str | None         # 频道名
    content: str                # 文本内容
    content_type: str           # text | code | decision | task | feedback
    reply_to: str | None        # 回复的消息 ID
    priority: str               # critical | high | normal | low
    timestamp: float
```

### 四种通信模式

| 模式 | 范围 | 示例 |
|------|------|------|
| **DM** | 1:1 | CEO → CTO: "技术方案定了吗？" |
| **Channel** | 1:N | #engineering 频道讨论 |
| **Meeting** | N:N | 每日站会 (LLM 主持) |
| **Announcement** | 1:All | "生产环境宕机！全体工程师..." |

### 前端 WebSocket 协议

```
后端 Hub (ws_manager)              前端 Phaser 3
      │                                  │
      │── {type: "agent_message",        │
      │    sender: "Alex",               │
      │    content: "早上好团队"}  ──────→│ 💬 气泡
      │                                  │
      │── {type: "agent_action",         │
      │    agent: "Jordan",              │
      │    action: "move_to",            │
      │    target: "whiteboard"} ───────→│ 🚶 走向白板
      │                                  │
      │── {type: "agent_created",        │
      │    name: "Taylor",               │
      │    role: "HR Director"} ────────→│ 🟢 新小人
      │                                  │
      │── {type: "meeting_start",        │
      │    participants: [...]} ────────→│ 🏢 走向会议室
      │                                  │
      │── {type: "state_snapshot",       │
      │    agents: [...], bank: 480000}─→│ 🔄 全量同步
```

---

## 七、LLM 统一网关

### 设计原则

> **API Key 只在 Company Hub 配一次。Agent 不感知自己用的是什么模型。**

```python
class LLMGateway:
    """公司级 LLM 网关"""

    def __init__(self, config: LLMConfig):
        self.default_model = config.default_model     # "gpt-4o-mini"
        self.models = config.models                    # 可用模型池
        self.daily_budget = config.daily_budget        # Token 预算
        self.usage_today = 0

        # 角色 → 模型路由规则
        self.routing = {
            "ceo":              "gpt-4o",
            "cto":              "claude-sonnet-4",
            "hr-director":      "gpt-4o",
            "senior-engineer":  "gpt-4o-mini",
            "junior-engineer":  "gpt-4o-mini",
            "designer":         "gpt-4o",
            "default":          "gpt-4o-mini",
        }

    async def chat(self, agent_profile: AgentProfile,
                   messages: list, tools: list) -> LLMResponse:
        # 1. 按角色选模型
        model = self.routing.get(agent_profile.role, self.routing["default"])

        # 2. 预算检查
        if self.usage_today > self.daily_budget:
            model = self._cheapest_model()

        # 3. 组装 System Prompt (身份 + Skills)
        system_prompt = await self._build_system_prompt(agent_profile)

        # 4. 调用 LLM
        response = await self._provider.chat(
            model=model,
            system=system_prompt,
            messages=messages,
            tools=tools,
        )

        self.usage_today += response.usage.total_tokens
        return response
```

### Agent System Prompt 动态组装

```python
async def _build_system_prompt(self, profile: AgentProfile) -> str:
    """每次 Agent 调 LLM 前，动态组装完整 System Prompt"""

    # 1. 基础身份
    base = profile.system_prompt

    # 2. 公司上下文
    context = await self._get_company_context(profile)

    # 3. Skills 注入 (按层级)
    skills = await self.skill_pool.get_effective_skills(
        agent_id=profile.agent_id,
        role=profile.role,
        department=profile.department,
    )
    skill_text = "\n\n".join(
        f"## Skill: {s.name}\n{s.prompt_injection}" for s in skills
    )

    return f"{base}\n\n{context}\n\n---\n\n{skill_text}"
```

---

## 八、Skill 管理体系

### 双层体系

```
┌─────────────────────────────────────────────────────────────┐
│            Company Skill Pool (Redis — Hub 管理)             │
│                                                             │
│  Level: COMPANY → 所有 Agent 自动继承                         │
│  Level: DEPARTMENT → 同部门自动继承                          │
│  Level: ROLE → 同角色的共享经验                              │
│  Level: PERSONAL → Agent 个人独有                            │
│                                                             │
│  管理: create / publish / deprecate / archive               │
│        search / recommend / share                           │
└───────────────────────────┬─────────────────────────────────┘
                            │ 双向同步
┌───────────────────────────┴─────────────────────────────────┐
│         Agent 容器内部: Hermes Skills 系统                    │
│                                                             │
│  ✅ 完成复杂任务 → 自动提取经验 → 新 Skill                    │
│  ✅ 使用反馈 → Skill 自我改进                                │
│  ✅ FTS5 全文搜索 → 找到最相关的 Skill                       │
│  ✅ 兼容 agentskills.io 标准                                 │
└─────────────────────────────────────────────────────────────┘
```

**职责分工**：Hermes 负责"学"(自动提取经验)，Company Pool 负责"管"(共享、分发、权限、版本)。

### Skill 数据模型

```python
@dataclass
class Skill:
    id: str
    name: str                    # "生产环境部署 Checklist"
    category: SkillCategory      # technical | management | creative | operations
    level: SkillLevel            # company | department | role | personal
    scope: list[str]             # 谁能用: ["senior-engineer", "junior-engineer"]
    description: str
    prompt_injection: str        # ★ 注入到 Agent System Prompt 的内容
    created_by: str              # 哪个 Agent 创建的
    created_from: str | None     # 从哪个任务中学到的
    usage_count: int
    rating: float
    status: str                  # draft | published | deprecated | archived
    version: int
    history: list[dict]          # 版本历史

class SkillCategory(Enum):
    TECHNICAL = "technical"
    MANAGEMENT = "management"
    CREATIVE = "creative"
    OPERATIONS = "operations"

class SkillLevel(Enum):
    COMPANY = "company"          # 全员继承
    DEPARTMENT = "department"    # 部门继承
    ROLE = "role"                # 同角色继承
    PERSONAL = "personal"        # 仅自己
```

### Skill 生命周期

```
               HR / Senior 主动创建
                     │
                     ▼
            ┌────────────────┐
            │   DRAFT        │  刚创建，待审核
            └───────┬────────┘
                    │ CTO / Team Lead 审核
                    ▼
            ┌────────────────┐
            │   PUBLISHED    │  供目标范围 Agent 使用
            └──┬─────────┬───┘
               │         │
        Agent 使用反馈  发现过时
               │         │
               ▼         ▼
        ┌──────────┐  ┌──────────────┐
        │ 评分上升  │  │  DEPRECATED  │
        │ 使用量+1  │  │  (已弃用)     │
        └──────────┘  └──────┬───────┘
                             │
                             ▼
                      ┌──────────────┐
                      │  ARCHIVED    │
                      └──────────────┘
```

### Skill 来源

| 来源 | 触发方式 | 示例 |
|------|----------|------|
| 预设 | 创建 Agent 时自带 | 新 Engineer 自带 "Python 开发" |
| 自动学习 | Hermes 完成复杂任务后自动提取 | 部署 5 次后自动生成 "部署 Checklist" |
| 上级传授 | Senior 调用 share_skill | CTO 把"架构审查规范"教给 Junior |
| 事后总结 | 项目复盘后提炼 | Sprint 回顾 → 生成"避免 X 类 Bug" |
| 主动学习 | Agent 调用 learn_skill | Junior 从公司池搜索"如何写单元测试" |

### 新 Agent 入职时的 Skill 继承

```python
async def onboard_agent(agent_id: str, role: str, department: str):
    """新 Agent 入职: 自动继承适用的 Skills"""

    skills = []

    # 1. 公司级 (所有 Agent)
    skills += await skill_pool.get_by_level("company")

    # 2. 部门级 (同部门)
    skills += await skill_pool.get_by_department(department)

    # 3. 角色级 (同角色共享经验)
    skills += await skill_pool.get_by_role(role)

    # 4. 预设 (角色自带基础技能)
    skills += PRESET_SKILLS.get(role, [])

    # 5. 推送到 Agent 容器
    await redis.publish(f"agent:{agent_id}:skills:init", {
        "skills": [s.to_dict() for s in skills]
    })
```

### Skill 同步机制

```
Agent 容器 (Hermes)                Company Hub (Skill Pool)
      │                                    │
      │── 完成复杂任务 ──→ 本地生成新 Skill   │
      │                                    │
      │── hub:skill:new ──────────────────→│  记录到公司池
      │   {skill, agent_id}               │  状态: draft
      │                                    │
      │                             CTO 审核 → published
      │                                    │
      │← agent:{id}:skills:pending ───────│  通知 Agent
      │   更新后的 Skill                    │
      │                                    │
      │── 使用反馈 ───────────────────────→│  更新评分
```

---

## 九、文件存储

### 方案：共享 Docker Volume

MVP 阶段使用 Docker Volume，所有 Agent 容器挂载同一个卷。

```
/workspace/shared/         ← 所有 Agent 容器挂载此目录
├── docs/                  # 公司文档
│   ├── strategy.md
│   ├── hiring-plan.md
│   └── meeting-notes/
│       └── 2026-01-15-standup.md
├── projects/              # 项目文件
│   └── mvp/
│       ├── src/
│       ├── tests/
│       ├── designs/
│       └── README.md
└── assets/                # 共享资源
    ├── logo.svg
    └── brand-guide.pdf
```

每个 Agent 还有自己的私有 workspace：

```
/workspace/{agent_id}/     ← Agent 私有目录
├── scratch/               # 草稿区
└── personal-notes/        # 个人笔记
```

### Agent 文件工具

```python
TOOLS_FILE = {
    "write_file": {
        "description": "写入文件到公司共享存储",
        "parameters": {
            "path": "相对于 /workspace/shared/ 的路径",
            "content": "文件内容",
        },
        "scope": "shared",    # shared | personal
    },
    "read_file": {
        "description": "从公司共享存储读取文件",
        "parameters": {"path": "..."},
    },
    "list_files": {
        "description": "列出目录内容",
        "parameters": {"path": "...", "recursive": "bool"},
    },
}
```

**后续演进**：当需要版本控制、权限隔离、前端预览时，将 Volume 替换为 MinIO S3 API，工具层只需改一个适配器。

---

## 十、前端 (像素风办公室)

### 技术栈

| 技术 | 用途 |
|------|------|
| **Phaser 3** | 2D 游戏引擎 — 像素风渲染、精灵动画、寻路 |
| **EasyStar.js** | A* 寻路 — Agent 在办公室中走动 |
| **React 19** | UI 组件 — HUD、面板、设置页 |
| **Tailwind CSS 4** | 像素风 UI 样式 |
| **WebSocket** | 实时状态同步 |
| **Howler.js** | 音效 (消息通知、环境音) |

### 场景布局

```
┌─────────────────────────────────────────────────────────────┐
│  💰 $480,000  │  📅 Day 7  │  😊 Mood: 78%  │  ⏩ 60x      │  ← HUD 顶栏
├──────────────────────┬──────────────────────────────────────┤
│                      │                                      │
│   ┌─工位区────────┐  │   ┌─会议室────────┐                  │
│   │ 🧑‍💼 🧑‍💻 🎨   │  │   │              │                  │
│   │ Alex Jordan   │  │   │   🪑🪑🪑🪑   │                  │
│   │  Mia   Sam    │  │   │   [站会中]    │                  │
│   │               │  │   │              │                  │
│   └───────────────┘  │   └──────────────┘                  │
│                      │                                      │
│   ┌─白板区──────┐   │   ┌─休闲区────┐                      │
│   │  📋 MVP计划  │   │   │ ☕️ 🛋️     │                      │
│   └──────────────┘   │   │ 饮水机    │                      │
│                      │   └──────────┘                      │
├──────────────────────┴──────────────────────────────────────┤
│  [CEO Alex]: "Taylor, 我们需要招聘 2 名工程师"              │  ← 日志底栏
└─────────────────────────────────────────────────────────────┘
```

### Agent 精灵动画状态机

```
              ┌──────────┐
    ┌────────→│  IDLE    │←────────┐
    │         │ (待机)    │         │
    │         └────┬─────┘         │
    │              │ 收到任务       │ 任务完成
    │              ↓               │
    │         ┌──────────┐         │
    │         │ WALKING  │         │
    │         │ (寻路中)  │         │
    │         └────┬─────┘         │
    │              │ 到达          │
    │              ↓               │
    │    ┌─────────────────┐      │
    │    │  WORKING        │──────┘
    │    │  💻 工位        │
    │    │  🪑 会议室       │
    │    │  📋 白板        │
    │    └────────┬────────┘
    │             │ 说话
    │             ↓
    │    ┌─────────────────┐
    └────│  TALKING        │
         │  💬 气泡        │
         └─────────────────┘
```

### 前端组件树

```
App
├── PhaserCanvas               # Phaser 3 渲染层
│   ├── OfficeScene             # 办公室主场景
│   │   ├── Tilemap (地板/家具)
│   │   ├── AgentSprite[]       # 每个 Agent 的像素精灵
│   │   ├── SpeechBubble[]      # 对话气泡
│   │   └── PathFinder (EasyStar)
│   └── MeetingScene            # 会议室特写
│
├── HUD                         # 顶栏 (React)
│   ├── FinanceBar              # 资金 + 月烧钱
│   ├── DateDisplay             # 仿真日期 + 时间流速
│   └── MoodIndicator           # 团队情绪均值
│
├── AgentPanel                  # 侧边栏 (React, 点击 Agent 弹出)
│   ├── AgentInfo               # 名字/角色/入职天数
│   ├── SkillList               # 拥有的 Skills
│   ├── MemoryTimeline          # 近期记忆时间线
│   └── ActionLog               # 近期动作流
│
├── CompanyDashboard            # 仪表盘 (React)
│   ├── OrgChartView            # 组织架构树
│   ├── EconomyChart            # 收支趋势图
│   └── ProjectBoard            # 项目看板
│
├── SettingsPage                # 设置页 (React)
│   ├── LLMConfig               # API Key + 模型路由
│   ├── SimulationControl       # 启停/速度/回放
│   └── SkillPoolManager        # Skill 池管理
│
├── LogFeed                     # 底栏 (React)
│   └── 实时日志流
│
└── ControlBar                  # 底栏控制 (React)
    ├── Play/Pause
    ├── SpeedControl (1x/10x/60x)
    └── Snapshot
```

---

## 十一、部署方案

### docker-compose.yml (完整)

```yaml
version: "3.8"

services:
  # ═══════════════════════════════════════════
  # 消息骨干
  # ═══════════════════════════════════════════
  redis:
    image: redis:7-alpine
    container_name: aisim-redis
    command: redis-server --appendonly yes --appendfsync everysec
    volumes:
      - redis_data:/data
    networks:
      - aisim-net
    restart: unless-stopped

  # ═══════════════════════════════════════════
  # Company Hub (前端 + 后端 + 仿真 + Agent编排)
  # ═══════════════════════════════════════════
  company:
    build:
      context: .
      dockerfile: Dockerfile.company
    container_name: aisim-company
    ports:
      - "3000:3000"    # Web UI
      - "8000:8000"    # WebSocket
    environment:
      - REDIS_URL=redis://redis:6379
      - LLM_PROVIDER=${LLM_PROVIDER:-openai}
      - LLM_API_KEY=${LLM_API_KEY}
      - LLM_MODEL=${LLM_MODEL:-gpt-4o-mini}
      - TICK_INTERVAL_MS=${TICK_INTERVAL_MS:-5000}
      - DOCKER_HOST=unix:///var/run/docker.sock
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - ./config:/app/config:ro
      - ./data:/app/data
      - company_workspace:/workspace/company
      - company_files:/workspace/shared       # ★ 共享文件
    networks:
      - aisim-net
    depends_on:
      - redis
    restart: unless-stopped

  # ═══════════════════════════════════════════
  # CEO Agent (公司创立时就存在)
  # ═══════════════════════════════════════════
  agent-ceo:
    build:
      context: .
      dockerfile: Dockerfile.agent
    container_name: aisim-agent-ceo
    environment:
      - REDIS_URL=redis://redis:6379
      - AGENT_ID=ceo-alex
    volumes:
      - agent_ceo_workspace:/workspace/ceo-alex
      - company_files:/workspace/shared       # ★ 共享文件
    networks:
      - aisim-net
    depends_on:
      - redis
      - company
    restart: unless-stopped

volumes:
  redis_data:
  company_workspace:
  company_files:            # ★ 共享文件卷
  agent_ceo_workspace:
  # ─── 其他 Agent 的 workspace 由 Company Hub 动态创建 ───

networks:
  aisim-net:
    driver: bridge
```

### Makefile

```makefile
# ═══ 启动 ═══
up:
	docker compose up -d

down:
	docker compose down

# ═══ 日志 ═══
logs:
	docker compose logs -f

logs-ceo:
	docker compose logs -f agent-ceo

# ═══ 重置 ═══
reset:
	docker compose down -v
	rm -rf data/

# ═══ 新增 Agent (手动，调试用) ═══
agent:
	docker run -d \
	  --name aisim-agent-$(NAME) \
	  --network aisim-net \
	  -e REDIS_URL=redis://redis:6379 \
	  -e AGENT_ID=$(NAME) \
	  -v aisim_agent_$(NAME):/workspace/$(NAME) \
	  -v aisim_company_files:/workspace/shared \
	  aisim-agent:latest
```

### 单行启动

```bash
# 配置 API Key
export LLM_API_KEY=sk-xxx

# 一键启动
docker compose up

# 浏览器打开 http://localhost:3000
# 看到像素风办公室，只有 CEO 一个人站在中央
```

---

## 十二、启动流程

```
T=0         docker compose up
            ├── redis 就绪
            ├── company Hub 就绪 (:3000 + :8000)
            └── agent:ceo 就绪 → 报到 → 领 Profile → 运行

T=1s        前端显示: 像素办公室，CEO 独自站在中央
            HUD: $500,000 / Day 1 / 👥 1人

T=30s       CEO 第一个 Tick:
            "公司刚创立，我需要一个 HR 总监"
            → 调用 create_agent(
                name="Taylor",
                role="HR Director",
                personality={C:0.9, E:0.7, A:0.85},
              )

T=35s       Company Hub:
            1. 生成 Taylor 的 Profile (system_prompt + tools + skills)
            2. docker run aisim-agent-hr-taylor
            3. 等待 Taylor 报到 → 下发 Profile → 等待 ready
            4. 通知前端 → 新像素小人出现在工位
            5. 扣减薪资预算

T=40s       前端: CEO (🧑‍💼) + HR (👩‍💼) 两人

T=2min      Taylor 第一个 Tick:
            "我是 HR 总监 Taylor。现在只有 2 人，急需工程师。"
            → 发消息给 CEO: "建议招聘 1 Senior + 1 Junior Engineer"
            ← CEO: "批准"

T=3min      Taylor:
            → create_agent(name="Jordan", role="Senior Engineer", salary=130000)
            → create_agent(name="Sam", role="Junior Engineer", salary=75000)

T=4min      前端: CEO + HR + Sr Eng + Jr Eng 四人
            HUD: $295,000 / Day 1 / 👥 4人

T=10min     Jordan 开始写代码
            Sam 向 Jordan 求助 → Jordan 教他 → Skill 传递
            公司正常运转中...
```

---

## 十三、项目结构

```
ai-sim-company/
├── config/
│   └── company.yaml              # 初始配置 (CEO + 资金 + LLM)
│
├── Dockerfile.company            # Company Hub 镜像
├── Dockerfile.agent              # Agent 基础镜像
├── docker-compose.yml
├── Makefile
├── README.md
│
├── aisim/                        # Python 包 (Backend)
│   ├── company/                  # Company Hub
│   │   ├── __init__.py
│   │   ├── hub.py                # CompanyHub 主类
│   │   ├── agent_manager.py      # Agent 生命周期 + Docker API
│   │   ├── profile_registry.py   # Agent Profile 管理
│   │   └── org_chart.py          # 组织架构
│   │
│   ├── agent/                    # Agent Runtime (容器内运行)
│   │   ├── __init__.py
│   │   ├── runtime.py            # Agent 主程序 (入口)
│   │   ├── memory.py             # MemoryManager
│   │   └── identity.py           # 身份 Prompt 生成
│   │
│   ├── simulation/               # 仿真引擎
│   │   ├── __init__.py
│   │   ├── clock.py              # Tick 时钟
│   │   ├── economy.py            # 经济系统
│   │   └── event_bus.py          # 事件系统
│   │
│   ├── comm/                     # 通信
│   │   ├── __init__.py
│   │   ├── message_bus.py        # Redis 消息路由
│   │   └── meeting.py            # 会议系统
│   │
│   ├── skills/                   # Skill 管理
│   │   ├── __init__.py
│   │   ├── pool.py               # Company Skill Pool
│   │   ├── sync.py               # Agent ↔ Hub 同步
│   │   └── preset.py             # 预设 Skills
│   │
│   ├── llm/                      # LLM 网关
│   │   ├── __init__.py
│   │   ├── gateway.py            # 统一 LLM 接入
│   │   ├── router.py             # 角色 → 模型路由
│   │   └── prompts/              # Prompt 模板
│   │       ├── ceo.j2
│   │       ├── hr_director.j2
│   │       ├── senior_engineer.j2
│   │       ├── junior_engineer.j2
│   │       ├── designer.j2
│   │       └── meeting.j2
│   │
│   ├── tools/                    # Agent 工具定义
│   │   ├── __init__.py
│   │   ├── create_agent.py       # ★ 创建 Agent (CEO/HR)
│   │   ├── send_message.py
│   │   ├── call_meeting.py
│   │   ├── file_ops.py           # 文件读写
│   │   ├── web_search.py
│   │   ├── share_skill.py
│   │   └── learn_skill.py
│   │
│   ├── api/                      # HTTP + WebSocket
│   │   ├── __init__.py
│   │   ├── server.py             # FastAPI 入口
│   │   ├── ws.py                 # WebSocket 管理
│   │   └── routes.py             # REST 路由
│   │
│   └── db.py                     # SQLite 持久化
│
├── frontend/                     # Next.js + Phaser 3
│   ├── package.json
│   ├── next.config.ts
│   ├── Dockerfile
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx
│   │   │   └── page.tsx
│   │   ├── game/                 # Phaser 3 核心
│   │   │   ├── index.ts
│   │   │   ├── scenes/
│   │   │   │   ├── BootScene.ts
│   │   │   │   ├── OfficeScene.ts
│   │   │   │   └── MeetingScene.ts
│   │   │   ├── sprites/
│   │   │   │   ├── AgentSprite.ts
│   │   │   │   └── SpeechBubble.ts
│   │   │   ├── pathfinding/
│   │   │   │   └── PathFinder.ts
│   │   │   └── map/
│   │   │       ├── OfficeMap.ts
│   │   │       └── tilesets/
│   │   ├── components/           # React UI
│   │   │   ├── HUD.tsx
│   │   │   ├── AgentPanel.tsx
│   │   │   ├── CompanyDashboard.tsx
│   │   │   ├── SettingsPage.tsx
│   │   │   ├── LogFeed.tsx
│   │   │   └── ControlBar.tsx
│   │   ├── hooks/
│   │   │   ├── useWebSocket.ts
│   │   │   └── useGameState.ts
│   │   └── types/
│   │       └── game.ts
│   └── public/
│       └── assets/
│           ├── sprites/          # 像素精灵图
│           ├── tilesets/         # 图块集
│           └── audio/            # 音效
│
├── docs/
│   └── ARCHITECTURE.md           # 本文档
│
└── tests/
```

---

## 十四、MVP 路线图

```
Phase 1: 基础设施 (2-3 weeks)
├── Dockerfile.agent + Dockerfile.company
├── docker-compose (redis + company + ceo)
├── Redis 通信骨干 (消息总线 + 通道)
├── Agent Runtime (报到→领Profile→Tick循环)
├── Agent Manager (Docker API 创建/销毁容器)
├── LLM Gateway (统一 API Key + 角色路由)
├── 简单 CLI 日志输出
└── CEO 能调用 create_agent 创建新 Agent

Phase 2: 像素风前端 (3-4 weeks)
├── Phaser 3 + Next.js 集成
├── 办公室 Tilemap (工位/会议室/休闲区)
├── AgentSprite (32×32 像素 + 动画状态机)
├── EasyStar A* 寻路
├── WebSocket 实时同步 (位置/状态/气泡)
├── HUD (资金/日期/KPI)
├── AgentPanel (点击查看详情)
├── 对话气泡 + 日志底栏
└── 控制栏 (播放/暂停/加速)

Phase 3: 业务深度 (3-4 weeks)
├── 经济系统 (收支/薪资/融资/破产)
├── 组织架构 (角色/部门/汇报线)
├── HR 招聘流程 (需求→候选→创建→入职)
├── Skill 管理体系 (公司池 + Hermes 同步 + 继承)
├── 会议系统 (LLM 主持 + 自动纪要)
├── 任务分解与分配
├── 市场事件 + 随机事件
├── 文件共享 (Volume 读写)
└── Agent 个人 workspace

Phase 4: 打磨 (2-3 weeks)
├── 仿真回放 + 分支对比
├── 音效 + 环境音
├── 性能优化 (50+ Agent)
├── 像素美术资产 polish
├── 场景模板库 (软件公司/营销公司/设计工作室)
├── SettingsPage (LLM 配置 UI)
└── 完整文档
```

---

## 附录：关键技术决策汇总

| 决策 | 选择 | 理由 |
|------|------|------|
| Agent 底层运行时 | Hermes Agent (Nous Research) | 现成的工具循环/记忆/技能/LLM 抽象 |
| Agent 通信 | Redis Pub/Sub | 轻量、可靠、跨容器、支持模式订阅 |
| Agent 容器 | Docker + 基础镜像 + AGENT_ID | 真正独立运行，一个参数定义身份 |
| LLM 管理 | Company Hub 统一网关 | 配一次，成本可控，按角色路由 |
| 文件存储 | 共享 Docker Volume | MVP 零依赖，后续换 MinIO 只需改适配器 |
| Skill 管理 | Hermes (学) + Company Pool (管) | 双层分工，自动学习 + 权限分发 |
| 前端 | Phaser 3 + React + WebSocket | 像素风 + 现代 UI + 实时同步 |
| 部署 | docker compose up | 一个命令启动一切 |
