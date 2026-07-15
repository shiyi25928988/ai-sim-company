"""web_search - 联网搜索 (见 §四 各角色工具)。"""

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
        # TODO: 接入搜索 API (httpx)
        return {"status": "ok", "query": kwargs.get("query"), "results": []}


register(WebSearchTool())
