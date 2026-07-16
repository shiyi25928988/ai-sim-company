"""Agent subpackage - the Agent Runtime that runs inside the container (see §四/§五).

This subpackage only executes inside the Agent container; the Hub should not import runtime.py (it depends on hermes).
"""

from __future__ import annotations

import os

__all__ = ["agent_id", "redis_url"]


def agent_id() -> str:
    """The Agent ID of the current container (startup parameter)."""
    return os.environ["AGENT_ID"]


def redis_url() -> str:
    """Redis connection URL (startup parameter)."""
    return os.environ["REDIS_URL"]
