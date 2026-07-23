"""Anthropic native provider - calls /v1/messages (Anthropic message format).

Converts OpenAI-style messages/tools (used by agent_runner) to Anthropic format and back,
so the rest of the system stays OpenAI-shaped. Selected when LLM_PROVIDER=anthropic.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

import httpx

from aisim.llm.provider import LLMError

logger = logging.getLogger(__name__)

ANTHROPIC_BASE_URL = "https://api.anthropic.com"
ANTHROPIC_VERSION = "2023-06-01"


class AnthropicProvider:
    """Anthropic native chat provider (/v1/messages)."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "",
        timeout: float = 60.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = (base_url or os.environ.get("LLM_BASE_URL", "") or ANTHROPIC_BASE_URL).rstrip("/")
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
        """Call /v1/messages and return an LLMResponse. Retries on 429."""
        from aisim.llm.gateway import LLMResponse  # lazy import to avoid circularity

        if not self.api_key:
            raise LLMError("LLM_API_KEY 未配置")

        payload: dict[str, Any] = {
            "model": model,
            "max_tokens": 4096,
            "system": system,
            "messages": self._convert_messages(messages),
        }
        if tools:
            payload["tools"] = [
                {
                    "name": t["function"]["name"],
                    "description": t["function"].get("description", ""),
                    "input_schema": t["function"].get("parameters") or {"type": "object", "properties": {}},
                }
                for t in tools
                if t.get("type") == "function" and t.get("function")
            ]

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        }
        url = f"{self.base_url}/v1/messages"

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
                wait = min(2 ** attempt, 16)
                logger.warning(
                    "Anthropic 429 rate limited, retry in %ss (attempt %d/%d)",
                    wait, attempt + 1, max_retries,
                )
                await asyncio.sleep(wait)
                continue

            if resp.status_code >= 400:
                raise LLMError(f"HTTP {resp.status_code}: {resp.text[:300]}")

            data = resp.json()
            return self._parse_response(data, model)

        raise LLMError(last_error or f"HTTP 429 after {max_retries} retries")

    @staticmethod
    def _convert_messages(messages: list[dict]) -> list[dict]:
        """Convert OpenAI-style messages to Anthropic format."""
        out: list[dict] = []
        for m in messages:
            role = m.get("role", "user")
            if role == "tool":
                # OpenAI tool result -> Anthropic user tool_result
                out.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": m.get("tool_call_id", ""),
                        "content": m.get("content", ""),
                    }],
                })
            elif role == "assistant":
                content: list[dict] = []
                if m.get("content"):
                    content.append({"type": "text", "text": m["content"]})
                for tc in (m.get("tool_calls") or []):
                    fn = tc.get("function", {}) if isinstance(tc, dict) else {}
                    raw_args = fn.get("arguments", "{}")
                    try:
                        args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                    except json.JSONDecodeError:
                        args = {}
                    content.append({
                        "type": "tool_use",
                        "id": tc.get("id", ""),
                        "name": fn.get("name", ""),
                        "input": args,
                    })
                out.append({"role": "assistant", "content": content or [{"type": "text", "text": ""}]})
            else:  # user
                out.append({"role": "user", "content": [{"type": "text", "text": m.get("content", "")}]})
        return out

    @staticmethod
    def _parse_response(data: dict, model: str):
        """Parse Anthropic response -> LLMResponse (OpenAI-shaped)."""
        from aisim.llm.gateway import LLMResponse

        blocks = data.get("content") or []
        text_parts: list[str] = []
        tool_calls: list[dict] = []
        for b in blocks:
            if b.get("type") == "text":
                text_parts.append(b.get("text", ""))
            elif b.get("type") == "tool_use":
                tool_calls.append({
                    "id": b.get("id", ""),
                    "type": "function",
                    "function": {
                        "name": b.get("name", ""),
                        "arguments": json.dumps(b.get("input", {})),
                    },
                })
        usage = data.get("usage") or {}
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        return LLMResponse(
            content="\n".join(text_parts),
            tool_calls=tool_calls or None,
            usage={
                "total_tokens": input_tokens + output_tokens,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            },
            model=data.get("model", model),
        )

    async def aclose(self) -> None:
        await self._client.aclose()
