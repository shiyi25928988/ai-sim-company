"""Hub 与 Agent 共享的契约: 数据模型 / Redis 通道名 / 配置。

放在 `shared/` 下的代码会被同时复制进 Company Hub 镜像与 Agent 镜像，
因此不得依赖 Hub 专属或 Agent 专属的模块。
"""
