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
        """Call /chat/completions and return an LLMResponse. Raises LLMError on failure.

        Retries on HTTP 429 (rate limit) with exponential backoff.
        """
        import asyncio

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

        max_retries = 4
        last_error: str | None = None
        for attempt in range(max_retries + 1):
            try:
                resp = await self._client.post(url, json=payload, headers=headers)
            except httpx.HTTPError as e:
                last_error = f"HTTP 错误: {e}"
                if attempt < max_retries:
                    await asyncio.sleep(min(2 ** attempt, 16))
                    continue
                raise LLMError(last_error) from e

            if resp.status_code == 429 and attempt < max_retries:
                # Prefer Retry-After header from the API (seconds or HTTP-date),
                # fall back to exponential backoff if missing/invalid
                retry_after = resp.headers.get("retry-after") or resp.headers.get("Retry-After")
                if retry_after:
                    try:
                        wait = int(retry_after)
                    except ValueError:
                        # Retry-After is a HTTP-date (e.g. "Wed, 21 Oct 2015 07:28:00 GMT")
                        import email.utils
                        from datetime import datetime, timezone
                        try:
                            retry_dt = email.utils.parsedate_to_datetime(retry_after)
                            wait = max(1, int((retry_dt - datetime.now(timezone.utc)).total_seconds()))
                        except Exception:
                            wait = min(2 ** attempt, 16)
                else:
                    wait = min(2 ** attempt, 16)
                wait = min(wait, 60)  # safety cap: never wait longer than 60s
                logger.warning(
                    "LLM 429 rate limited, retry in %ss (attempt %d/%d)%s",
                    wait, attempt + 1, max_retries,
                    " (Retry-After)" if retry_after else "",
                )
                await asyncio.sleep(wait)
                continue

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

        raise LLMError(last_error or f"HTTP 429 after {max_retries} retries")

    async def aclose(self) -> None:
        await self._client.aclose()
