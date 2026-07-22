"""code_review - a senior reviews a workspace file for correctness/quality (LLM review)."""

from __future__ import annotations

from aisim.tools import BaseTool, register


class CodeReviewTool(BaseTool):
    name = "code_review"
    description = (
        "Review a file in the workspace for correctness, edge cases, readability, and test coverage. "
        "Returns a concise review. Use it to ensure output quality before marking work done."
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Relative path under the workspace scope"},
            "scope": {"type": "string", "enum": ["shared", "personal"]},
        },
        "required": ["path"],
    }

    async def execute(self, **kwargs):  # type: ignore[override]
        # Executed by SimulatedAgentRunner._execute_tool (LLM review via LLMGateway).
        return {"status": "ok", "path": kwargs.get("path")}


register(CodeReviewTool())
