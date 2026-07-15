"""配置加载 - 合并 config/company.yaml 与环境变量。

${VAR} 占位符由环境变量替换; 缺失时回退到默认值。
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
    """LLM 统一网关配置 (见 §七)。API Key 只在这里配一次。"""

    provider: str = "openai"
    api_key: str = ""
    base_url: str = ""  # OpenAI 兼容端点; 空则用官方 https://api.openai.com/v1
    default_model: str = "gpt-4o-mini"
    daily_budget: int = 2_000_000  # 每日 Token 预算
    enable_tools: bool = True  # 是否向 LLM 发送 function-calling 工具 (端点不支持时关掉)
    max_iters: int = 3  # 单个 Agent 单 tick 内 LLM<->工具 的最大循环轮数 (控成本)
    routing: dict[str, str] = field(default_factory=dict)  # 角色 -> 模型


@dataclass
class SimulationConfig:
    tick_interval_ms: int = 5000
    auto_start: bool = False  # 启动即跑时钟? 默认 False (暂停，手动 play，控成本)
    agent_think_every: int = 1  # Agent 每 N 个 tick 思考一次 (1=每次; 控成本)
    agent_step_delay_ms: int = 800  # 单步模式下 Agent 之间的间隔 (ms，控节奏)


@dataclass
class CompanyConfig:
    name: str = "Acme AI Inc."
    initial_capital: int = 500_000


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
        """Redis 连接地址。

        优先用 REDIS_URL (可含密码，如 redis://:123456@localhost:6379/0)。
        否则由 REDIS_HOST/REDIS_PORT/REDIS_PASSWORD/REDIS_DB 拼装，
        便于本地开发 (宿主机 Redis 带密码) 与容器内 (compose 设 REDIS_URL) 两种场景。
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
        """Agent 容器后端: simulated (本地开发默认) | docker (生产)。"""
        return os.environ.get("AGENT_BACKEND", "simulated").lower()


def _expand(value: str) -> str:
    """把 ${VAR} 替换为环境变量值，未设置时保留空串。"""
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
    """读取 d[key]; 若为缺失或空串 (未设置的 ${VAR}) 则回退 default。"""
    v = d.get(key, default)
    return default if v in (None, "") else v


def load_config(path: str | Path = "config/company.yaml") -> Config:
    """从 YAML 加载配置并展开 ${VAR} 占位符。"""
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
            api_key=llm_raw.get("api_key", ""),  # 空串合法 (未配置 Key)
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
