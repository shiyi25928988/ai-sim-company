"""Agent 子包 - 容器内运行的 Agent Runtime (见 §四/§五)。

本子包仅在 Agent 容器内执行; Hub 不应导入 runtime.py (其依赖 hermes)。
"""

from __future__ import annotations

import os

__all__ = ["agent_id", "redis_url"]


def agent_id() -> str:
    """当前容器的 Agent 身份证号 (启动参数)。"""
    return os.environ["AGENT_ID"]


def redis_url() -> str:
    """Redis 连接地址 (启动参数)。"""
    return os.environ["REDIS_URL"]
