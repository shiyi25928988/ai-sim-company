"""LLM Provider - OpenAI 兼容 (见 §七)。

用 httpx 直连任意 OpenAI 兼容的 /chat/completions 端点:
- 官方 OpenAI (base_url=https://api.openai.com/v1)
- 代理 (one-api / new-api，可同时转发 gpt 与 claude 系列)
- 国产 OpenAI 兼容服务 (DeepSeek / 智谱 GLM / Moonshot 等)

Agent 不感知 provider; 只需 Company Hub 配一次 LLM_API_KEY (与可选 LLM_BASE_URL)。
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://api.openai.com/v1"


class LLMError(RuntimeError):
    """LLM 调用失败 (HTTP / 鉴权 / 解析)。"""


class OpenAICompatibleProvider:
    """OpenAI 兼容的 chat completions provider。"""

    def __init__(
        self,
        api_key: str,
        base_url: str = "",
        timeout: float = 60.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.api_key = api_key
        # base_url 优先级: 显式传入 > LLM_BASE_URL 环境变量 > 官方默认
        self.base_url = (base_url or os.environ.get("LLM_BASE_URL", "") or DEFAULT_BASE_URL).rstrip("/")
        self.timeout = timeout
        client_kwargs: dict[str, Any] = {"timeout": timeout}
        if transport is not None:
            client_kwargs["transport"] = transport
        self._client = httpx.AsyncClient(**client_kwargs)

    async def chat(
        self,
        model: str,
        system: str,
        messages: list[dict],
        tools: list[dict] | None = None,
    ):
        """调用 /chat/completions，返回 LLMResponse。失败抛 LLMError。"""
        from aisim.llm.gateway import LLMResponse  # 延迟导入避免循环

        if not self.api_key:
            raise LLMError("LLM_API_KEY 未配置")

        payload: dict[str, Any] = {
            "model": model,
            "messages": [{"role": "system", "content": system}, *messages],
        }
        if tools:
            payload["tools"] = tools

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        url = f"{self.base_url}/chat/completions"
        try:
            resp = await self._client.post(url, json=payload, headers=headers)
        except httpx.HTTPError as e:
            raise LLMError(f"HTTP 错误: {e}") from e

        if resp.status_code >= 400:
            raise LLMError(f"HTTP {resp.status_code}: {resp.text[:300]}")

        try:
            data = resp.json()
        except ValueError as e:
            raise LLMError(f"响应非 JSON: {resp.text[:300]}") from e

        choices = data.get("choices") or []
        if not choices:
            raise LLMError(f"响应无 choices: {str(data)[:300]}")

        message = choices[0].get("message", {})
        usage = data.get("usage") or {}
        return LLMResponse(
            content=message.get("content") or "",
            tool_calls=message.get("tool_calls"),
            usage=usage,
            model=data.get("model", model),
        )

    async def aclose(self) -> None:
        await self._client.aclose()
