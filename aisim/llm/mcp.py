"""MCP (Model Context Protocol) client manager.

Connects agents to external MCP servers (stdio or sse) and exposes each server's tools
as agent tools named `mcp_{server}_{tool}`. The Hub owns one MCPClientManager; agent_runner
routes any `mcp_*` tool call to it.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)


class MCPClientManager:
    """Manages connections to external MCP servers and exposes their tools to agents."""

    def __init__(self) -> None:
        self._servers: dict[str, dict] = {}  # name -> config
        self._sessions: dict[str, Any] = {}  # name -> ClientSession
        self._contexts: dict[str, Any] = {}  # name -> (transport_ctx, session_cm)
        self._tools: dict[str, list[dict]] = {}  # name -> OpenAI function schemas

    def configure(self, servers: list[dict]) -> None:
        """Set the desired server config (names -> config dict)."""
        self._servers = {s["name"]: s for s in servers if s.get("name")}

    async def connect(self, name: str) -> bool:
        """Connect to one MCP server (stdio or sse) and list its tools. Returns success."""
        cfg = self._servers.get(name)
        if not cfg:
            return False
        await self.disconnect(name)
        transport = cfg.get("transport", "stdio")
        transport_ctx = None
        session = None
        try:
            logger.info("MCP connect '%s': transport=%s", name, transport)
            if transport == "sse":
                from mcp.client.sse import sse_client

                logger.info("MCP '%s': sse url=%s", name, cfg.get("url"))
                transport_ctx = sse_client(cfg["url"])
                read, write = await transport_ctx.__aenter__()
            elif transport in ("streamableHttp", "streamable_http"):
                from mcp.client.streamable_http import streamablehttp_client

                logger.info("MCP '%s': streamableHttp url=%s", name, cfg.get("url"))
                transport_ctx = streamablehttp_client(cfg["url"])
                read, write, _ = await transport_ctx.__aenter__()
            else:
                import shlex
                import sys

                from mcp.client.stdio import StdioServerParameters, stdio_client

                logger.info("MCP '%s': stdio command=%s", name, cfg.get("command"))
                parts = shlex.split(cfg.get("command", ""))
                command = parts[0] if parts else ""
                args = list(cfg.get("args", []) or []) + parts[1:]
                # Windows: .cmd/.bat scripts (npx, npm) can't be launched by CreateProcess
                # directly; wrap with `cmd /c` so the shell resolves them.
                if sys.platform == "win32":
                    args = ["/c", command, *args]
                    command = "cmd"
                logger.info("MCP '%s': resolved command=%s args=%s", name, command, args)
                params = StdioServerParameters(command=command, args=args, env=cfg.get("env"))
                transport_ctx = stdio_client(params)
                read, write = await transport_ctx.__aenter__()
            from mcp import ClientSession

            session_cm = ClientSession(read, write)
            session = await session_cm.__aenter__()
            logger.info("MCP '%s': session created, initializing...", name)
            await session.initialize()
            logger.info("MCP '%s': initialized, listing tools...", name)
            tools_resp = await session.list_tools()
            self._sessions[name] = session
            self._contexts[name] = (transport_ctx, session_cm)
            self._tools[name] = [
                self._tool_to_schema(name, t) for t in (tools_resp.tools or [])
            ]
            logger.info("MCP server '%s' connected: %d tools", name, len(self._tools[name]))
            return True
        except Exception as e:  # noqa: BLE001
            logger.exception("MCP connect '%s' failed: %s", name, e)
            # cleanup partial
            if session is not None:
                try:
                    await session.__aexit__(None, None, None)
                except Exception:  # noqa: BLE001
                    pass
            if transport_ctx is not None:
                try:
                    await transport_ctx.__aexit__(None, None, None)
                except Exception:  # noqa: BLE001
                    pass
            return False

    async def connect_all(self) -> None:
        """Connect to all configured servers (best-effort, parallel)."""
        if not self._servers:
            return
        await asyncio.gather(
            *(self.connect(n) for n in list(self._servers)), return_exceptions=True
        )

    async def disconnect(self, name: str) -> None:
        session = self._sessions.pop(name, None)
        if session is not None:
            try:
                await session.__aexit__(None, None, None)
            except Exception:  # noqa: BLE001
                pass
        ctx_pair = self._contexts.pop(name, None)
        if ctx_pair is not None:
            transport_ctx, _ = ctx_pair
            try:
                await transport_ctx.__aexit__(None, None, None)
            except Exception:  # noqa: BLE001
                pass
        self._tools.pop(name, None)

    async def disconnect_all(self) -> None:
        for name in list(self._sessions):
            await self.disconnect(name)

    def list_all_tools(self) -> list[dict]:
        """All tools from all connected servers (OpenAI function schemas)."""
        out: list[dict] = []
        for tools in self._tools.values():
            out.extend(tools)
        return out

    def servers_status(self) -> list[dict]:
        """Status of each configured server."""
        return [
            {
                "name": n,
                "transport": s.get("transport", "stdio"),
                "url": s.get("url"),
                "command": s.get("command"),
                "connected": n in self._sessions,
                "tools": [t["function"]["name"] for t in self._tools.get(n, [])],
            }
            for n, s in self._servers.items()
        ]

    async def call_tool(self, tool_name: str, args: dict) -> str:
        """Call an MCP tool. tool_name = mcp_{server}_{tool}."""
        if not tool_name.startswith("mcp_"):
            return f"invalid mcp tool name: {tool_name}"
        rest = tool_name[4:]
        idx = rest.find("_")
        if idx <= 0:
            return f"invalid mcp tool name: {tool_name}"
        server = rest[:idx]
        tool = rest[idx + 1:]
        session = self._sessions.get(server)
        if session is None:
            return f"mcp server '{server}' not connected"
        try:
            result = await session.call_tool(tool, args or {})
            texts = [c.text for c in (result.content or []) if hasattr(c, "text")]
            return "\n".join(texts) if texts else str(result)
        except Exception as e:  # noqa: BLE001
            logger.exception("MCP call_tool '%s' failed: %s", tool_name, e)
            return f"mcp tool '{tool_name}' failed: {e}"

    @staticmethod
    def _tool_to_schema(server: str, tool: Any) -> dict:
        """Convert an MCP tool to an OpenAI function schema (name = mcp_{server}_{tool})."""
        name = f"mcp_{server}_{tool.name}"
        schema = getattr(tool, "inputSchema", None) or {"type": "object", "properties": {}}
        return {
            "type": "function",
            "function": {
                "name": name,
                "description": f"[MCP/{server}] {tool.description or tool.name}",
                "parameters": schema,
            },
        }
