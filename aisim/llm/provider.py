"""LLM Provider - OpenAI compatible (see §七).

Uses httpx to talk directly to any OpenAI-compatible /chat/completions endpoint:
- Official OpenAI (base_url=https://api.openai.com/v1)
- Proxies (one-api / new-api, can forward both gpt and claude families)
- Domestic OpenAI-compatible services (DeepSeek / Zhipu GLM / Moonshot etc.)

Agents are unaware of the provider; Company Hub only needs LLM_API_KEY configured once (plus optional LLM_BASE_URL).
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://api.openai.com/v1"


class LLMError(RuntimeError):
    """LLM call failure (HTTP / auth / parsing)."""


class OpenAICompatibleProvider:
    """OpenAI-compatible chat completions provider."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "",
        timeout: float = 60.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.api_key = api_key
        # base_url precedence: explicit arg > LLM_BASE_URL env var > official default
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
        """Call /chat/completions and return an LLMResponse. Raises LLMError on failure."""
        from aisim.llm.gateway import LLMResponse  # lazy import to avoid circularity

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
