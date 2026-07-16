"""web_search - online search (see §四 per-role tools)."""

from __future__ import annotations

from aisim.tools import BaseTool, register


class WebSearchTool(BaseTool):
    name = "web_search"
    description = "搜索互联网获取最新信息。"
    parameters = {
        "type": "object",
        "properties": {"query": {"type": "string"}, "limit": {"type": "integer"}},
        "required": ["query"],
    }

    async def execute(self, **kwargs):  # type: ignore[override]
        # TODO: integrate a search API (httpx)
        return {"status": "ok", "query": kwargs.get("query"), "results": []}


register(WebSearchTool())
