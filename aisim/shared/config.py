"""Config loading - merges config/company.yaml with environment variables.

${VAR} placeholders are replaced by environment variables; falls back to defaults when missing.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

_ENV_PATTERN = re.compile(r"\$\{([A-Z_][A-Z0-9_]*)\}")


@dataclass
class LLMConfig:
    """Unified LLM gateway config (see §七). The API Key is configured only here."""

    provider: str = "openai"
    api_key: str = ""
    base_url: str = ""  # OpenAI-compatible endpoint; empty uses official https://api.openai.com/v1
    default_model: str = "gpt-4o-mini"
    daily_budget: int = 2_000_000  # Daily token budget
    enable_tools: bool = True  # Whether to send function-calling tools to the LLM (turn off if the endpoint does not support them)
    max_iters: int = 3  # Max LLM<->tool loop rounds for a single Agent in a single tick (cost control)
    routing: dict[str, str] = field(default_factory=dict)  # Role -> model


@dataclass
class SimulationConfig:
    tick_interval_ms: int = 5000
    auto_start: bool = False  # Run the clock on startup? Default False (paused, manual play, cost control)
    agent_think_every: int = 1  # Agent thinks once every N ticks (1=every time; cost control)
    agent_step_delay_ms: int = 800  # Interval between Agents in step mode (ms, pace control)


@dataclass
class CompanyConfig:
    name: str = "Acme AI Inc."
    initial_capital: int = 500_000
    business_description: str = ""  # What the company does - injected into the CEO's tick prompt
    monthly_budget: int = 0  # Monthly budget cap (0 = unlimited)


@dataclass
class CEOConfig:
    agent_id: str = "ceo-alex"
    name: str = "Alex"
    role: str = "ceo"
    department: str = "Executive"
    salary: int = 0


@dataclass
class Config:
    company: CompanyConfig = field(default_factory=CompanyConfig)
    ceo: CEOConfig = field(default_factory=CEOConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    simulation: SimulationConfig = field(default_factory=SimulationConfig)

    @property
    def redis_url(self) -> str:
        """Redis connection URL.

        Prefers REDIS_URL (may include a password, e.g. redis://:123456@localhost:6379/0).
        Otherwise assembled from REDIS_HOST/REDIS_PORT/REDIS_PASSWORD/REDIS_DB,
        to suit both local development (host Redis with password) and in-container (compose sets REDIS_URL) scenarios.
        """
        url = os.environ.get("REDIS_URL")
        if url:
            return url
        host = os.environ.get("REDIS_HOST", "localhost")
        port = os.environ.get("REDIS_PORT", "6379")
        db = os.environ.get("REDIS_DB", "0")
        password = os.environ.get("REDIS_PASSWORD", "")
        if password:
            return f"redis://:{password}@{host}:{port}/{db}"
        return f"redis://{host}:{port}/{db}"

    @property
    def agent_backend(self) -> str:
        """Agent container backend: simulated (local dev default) | docker (production)."""
        return os.environ.get("AGENT_BACKEND", "simulated").lower()


def _expand(value: str) -> str:
    """Replace ${VAR} with the environment variable value; keeps an empty string if unset."""
    return _ENV_PATTERN.sub(lambda m: os.environ.get(m.group(1), ""), value)


def _expand_tree(node):
    if isinstance(node, dict):
        return {k: _expand_tree(v) for k, v in node.items()}
    if isinstance(node, list):
        return [_expand_tree(v) for v in node]
    if isinstance(node, str):
        return _expand(node)
    return node


def _val(d: dict, key: str, default):
    """Read d[key]; falls back to default if missing or empty string (unset ${VAR})."""
    v = d.get(key, default)
    return default if v in (None, "") else v


def load_config(path: str | Path = "config/company.yaml") -> Config:
    """Load config from YAML and expand ${VAR} placeholders."""
    path = Path(path)
    raw: dict = {}
    if path.exists():
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    raw = _expand_tree(raw)

    llm_raw = raw.get("llm", {})
    sim_raw = raw.get("simulation", {})
    company_raw = raw.get("company", {})
    ceo_raw = raw.get("ceo", {})

    return Config(
        company=CompanyConfig(
            name=_val(company_raw, "name", "Acme AI Inc."),
            initial_capital=int(_val(company_raw, "initial_capital", 500_000)),
            business_description=_val(company_raw, "business_description", ""),
            monthly_budget=int(_val(company_raw, "monthly_budget", 0)),
        ),
        ceo=CEOConfig(
            agent_id=_val(ceo_raw, "agent_id", "ceo-alex"),
            name=_val(ceo_raw, "name", "Alex"),
            role=_val(ceo_raw, "role", "ceo"),
            department=_val(ceo_raw, "department", "Executive"),
            salary=int(_val(ceo_raw, "salary", 0)),
        ),
        llm=LLMConfig(
            provider=_val(llm_raw, "provider", "openai"),
            api_key=llm_raw.get("api_key", ""),  # Empty string is valid (Key not configured)
            base_url=_val(llm_raw, "base_url", ""),
            default_model=_val(llm_raw, "default_model", "gpt-4o-mini"),
            daily_budget=int(_val(llm_raw, "daily_budget", 2_000_000)),
            enable_tools=str(_val(llm_raw, "enable_tools", "true")).lower()
            in ("1", "true", "yes", "on"),
            max_iters=int(_val(llm_raw, "max_iters", 3)),
            routing=llm_raw.get("routing", {}) or {},
        ),
        simulation=SimulationConfig(
            tick_interval_ms=int(_val(sim_raw, "tick_interval_ms", 5000)),
            auto_start=str(_val(sim_raw, "auto_start", "false")).lower()
            in ("1", "true", "yes", "on"),
            agent_think_every=int(_val(sim_raw, "agent_think_every", 1)),
            agent_step_delay_ms=int(_val(sim_raw, "agent_step_delay_ms", 800)),
        ),
    )
