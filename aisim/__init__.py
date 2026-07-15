"""ai-sim-company 后端包。

Company Hub (中枢) 与 Agent Runtime (容器内) 共用本包。
子包划分见 README / 架构设计文档 §十三。
"""

from __future__ import annotations

__version__ = "0.1.0"

# 启动时自动加载仓库根目录的 .env (本地 `uvicorn` 直跑时生效)。
# docker compose 自带 .env 读取，此处补齐非容器场景。
# 已存在的环境变量优先 (override=False)，故 shell/env 仍可覆盖 .env。
try:
    from pathlib import Path

    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass  # python-dotenv 未装时静默跳过，保持包可导入
