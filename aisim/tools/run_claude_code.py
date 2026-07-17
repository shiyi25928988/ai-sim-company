"""run_claude_code - invoke the Claude Code CLI in the workspace (when enabled)."""

from __future__ import annotations

from aisim.tools import BaseTool, register


class RunClaudeCodeTool(BaseTool):
    name = "run_claude_code"
    description = (
        "Run a Claude Code CLI task in the workspace (write/refactor code, run tests, analyze). "
        "Only available when enabled in /settings; runs non-interactively with the given prompt."
    )
    parameters = {
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "The task for Claude Code, e.g. 'add unit tests for auth.py'",
            },
        },
        "required": ["prompt"],
    }

    async def execute(self, **kwargs):  # type: ignore[override]
        # Executed by SimulatedAgentRunner._execute_tool.
        return {"status": "ok", "prompt": kwargs.get("prompt")}


register(RunClaudeCodeTool())
