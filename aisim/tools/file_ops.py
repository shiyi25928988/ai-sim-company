"""file_ops - workspace file read/write (see §九 file storage).

In simulated mode these tools are executed by SimulatedAgentRunner._execute_tool,
which writes to hub.config.company.workspace_dir (shared/ or {agent_id}/).
"""

from __future__ import annotations

from aisim.tools import BaseTool, register


class WriteFileTool(BaseTool):
    name = "write_file"
    description = "Write a file to the company workspace (produced docs / code / assets)."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Relative path under the workspace scope"},
            "content": {"type": "string"},
            "scope": {
                "type": "string",
                "enum": ["shared", "personal"],
                "description": "shared = company-wide; personal = only this agent",
            },
        },
        "required": ["path", "content"],
    }

    async def execute(self, **kwargs):  # type: ignore[override]
        # Executed by SimulatedAgentRunner._execute_tool in simulated mode.
        return {"status": "written", "path": kwargs.get("path")}


class ReadFileTool(BaseTool):
    name = "read_file"
    description = "Read a file from the company workspace."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "scope": {"type": "string", "enum": ["shared", "personal"]},
        },
        "required": ["path"],
    }

    async def execute(self, **kwargs):  # type: ignore[override]
        return {"status": "ok", "path": kwargs.get("path"), "content": ""}


class ListFilesTool(BaseTool):
    name = "list_files"
    description = "List files in a workspace directory."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "scope": {"type": "string", "enum": ["shared", "personal"]},
            "recursive": {"type": "boolean"},
        },
        "required": ["path"],
    }

    async def execute(self, **kwargs):  # type: ignore[override]
        return {"status": "ok", "path": kwargs.get("path"), "files": []}


register(WriteFileTool())
register(ReadFileTool())
register(ListFilesTool())
