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
init.bat                         :: 检查 Python/Node/Redis，装依赖，编译前端
copy .env.example .env           :: 填 LLM_API_KEY（+ 可选 LLM_MODEL / LLM_BASE_URL）
```

### 运行

```bat
start.bat                        :: 启动 Redis + 后端(:8000) + 前端(:3000)
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

- **`.env`** - `LLM_API_KEY`（必需），`LLM_MODEL` / `LLM_BASE_URL` / `LLM_PROVIDER`（OpenAI 兼容端点如 DeepSeek），Redis，仿真速度。
- **`config/company.yaml`** - 业务（名称/描述/预算/工作区），CEO，LLM 路由，MCP server。`/setup` 页写 `company` 段。
