# ai-sim-company

> 多智能体 AI 公司模拟。配置业务，CEO（LLM 驱动）自主经营--招聘、派活、开会、产出--实时看板观察。

[English](./README.md)

## 原理

你设定业务（名称/描述/预算）。CEO agent 通过 LLM 自主经营公司：

- **CEO** 招聘 HR 总监，之后专注战略与委派。
- **HR** 先招聘产品经理。
- **产品经理** 分析业务，向 HR 提人员需求（如"2 名高级工程师、1 名设计师"）。
- **HR** 按产品经理的需求招聘。
- **工程师/设计师** 领取任务，在共享工作区产出文件（代码/文档/资产），测试/审查验证后标记完成。
- 全员通过消息与会议沟通；仿真时钟推进；看板实时展示。

Agent 每 tick 调用工具做真实决策（`create_agent` / `send_message` / `create_task` / `call_meeting` / `write_file` / `run_claude_code` / `code_review` / `find_skill` / `mcp_*`）。你是观察者--不直接控制 agent，但可随时在主控台给 CEO 下达指令。

LLM API Key 只配一次，agent 不感知。

## 使用

### 一次性初始化

```bat
init.bat                         :: 检查 Python/Node/MCP 工具，装依赖，编译前端
copy .env.example .env           :: 填 LLM_API_KEY（+ 可选 LLM_MODEL / LLM_BASE_URL）
```

### 运行

```bat
start.bat                        :: 启动 后端(:8000) + 前端(:3000)
stop.bat                         :: 停止服务
reset.bat                        :: 清数据重来
```

打开 http://localhost:3000：

1. **/setup** - 配置业务（名称、描述、资金、月预算、工作区目录）-> Apply（重置模拟，重新 seed CEO）。
2. **主控台(/)** - ▶ Play / ⏭ Step，看日志（可过滤）、任务、agent 面板。用 **📢 CEO 指令** 给 CEO 下达指令。
3. **/agents** - 查看团队，雇佣 agent，点进 agent 详情。
4. **/skills** - 管理 skill：创建/粘贴 JSON/从 URL 安装/上传 .zip（SKILL.md + .py）。编辑/删除。Agent 继承 skill，可查找/创建/分享。
5. **/mcp** - 配置外部 MCP server（stdio / sse / streamableHttp）。其工具对所有 agent 可用。
6. **/files** - 浏览工作区（agent 产出的代码/文档/资产）。
7. **/dashboard** - 收支、LLM 用量、团队、项目看板。
8. **/settings** - LLM 配置（只读），Claude Code 启用开关。

### CEO 指令

主控台点 **📢 CEO 指令** -> 输入指令（如"增加任务：实现登录"、"本周聚焦性能"）-> CEO 下 tick 据此行动。

## 配置

### `.env`（环境变量）

复制 `.env.example` 为 `.env` 并填值。后端启动时自动加载。这些变量通过 `config/company.yaml` 的 `${VAR}` 占位符引用。

| 变量 | 必需 | 默认 | 说明 |
|---|---|---|---|
| `LLM_API_KEY` | 是 | - | LLM API Key（只配一次，agent 不感知）。 |
| `LLM_PROVIDER` | 否 | `openai` | 接口类型：`openai`（OpenAI 兼容 `/chat/completions`）或 `anthropic`（原生 `/v1/messages`）。 |
| `LLM_MODEL` | 否 | `gpt-4o-mini` | 默认模型。 |
| `LLM_BASE_URL` | 否 | （官方 OpenAI） | OpenAI 兼容端点。DeepSeek: `https://api.deepseek.com/v1`；智谱: `https://open.bigmodel.cn/api/paas/v4`；one-api: `http://localhost:3000/v1`。 |
| `LLM_TOOLS_ENABLED` | 否 | `true` | 启用 function-calling（agent 工具调用）。端点不支持时设 `false`（agent 仍思考，纯文本）。 |
| `LLM_MAX_ITERS` | 否 | `3` | 单 agent 单 tick 的 LLM<->工具最大循环轮数。`1` 最省；`3` 可连续调多工具。 |
| `LLM_DAILY_BUDGET` | 否 | `2000000` | 每日 token 预算（成本上限）。`0`/负数 = 无限。 |
| `LLM_RPM_LIMIT` | 否 | `0` | 每分钟请求数上限。`0` = 无限。设为 API key 实际限速可避免 429。 |
| `AGENT_BACKEND` | 否 | `simulated` | `simulated`（本地开发）或 `docker`（生产）。 |
| `TICK_INTERVAL_MS` | 否 | `5000` | 仿真 tick 间隔（毫秒）。越大越慢，LLM 成本越低。 |
| `SIM_AUTO_START` | 否 | `false` | `true` = 启动即跑；`false` = 暂停（手动 Play）。 |
| `AGENT_THINK_EVERY` | 否 | `1` | Agent 每 N tick 思考一次。`1` = 每次；调大省成本。 |
| `AGENT_STEP_DELAY_MS` | 否 | `800` | 单步模式下 agent 间间隔（毫秒）。 |

#### LLM 接口

支持两种接口类型，由 `LLM_PROVIDER` 选择：

- **`openai`**（默认）- OpenAI 兼容 `/chat/completions`。支持 OpenAI、DeepSeek、智谱、Moonshot、Qwen、one-api/new-api、OpenRouter 等。设 `LLM_BASE_URL` 为端点。
- **`anthropic`** - Anthropic 原生 `/v1/messages`。直连 Claude 官方 API。`LLM_BASE_URL` 留空。

系统内部用 OpenAI 消息格式；选 `anthropic` 时消息/工具自动转换。

**DeepSeek 示例：**
```
LLM_API_KEY=sk-...
LLM_MODEL=deepseek-v4-flash
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_PROVIDER=openai
LLM_RPM_LIMIT=60
```

**Anthropic（Claude）示例：**
```
LLM_API_KEY=sk-ant-...
LLM_MODEL=claude-sonnet-5
LLM_PROVIDER=anthropic
LLM_BASE_URL=
```

### `config/company.yaml`

业务（名称/描述/预算/工作区），CEO，LLM 路由，MCP server。`/setup` 页写 `company` 段；MCP server 在 `/mcp` 页管理。
