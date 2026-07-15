"""file_ops - 共享文件读写 (见 §九 文件存储)。"""

from __future__ import annotations

from aisim.tools import BaseTool, register

SHARED_ROOT = "/workspace/shared"
PERSONAL_ROOT_TEMPLATE = "/workspace/{agent_id}"


class WriteFileTool(BaseTool):
    name = "write_file"
    description = "写入文件到公司共享存储 (/workspace/shared)。"
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "相对于 /workspace/shared/ 的路径"},
            "content": {"type": "string"},
            "scope": {"type": "string", "enum": ["shared", "personal"]},
        },
        "required": ["path", "content"],
    }

    async def execute(self, **kwargs):  # type: ignore[override]
        # TODO: 解析路径并写入 Volume (防越界)
        return {"status": "written", "path": kwargs.get("path")}


class ReadFileTool(BaseTool):
    name = "read_file"
    description = "从公司共享存储读取文件。"
    parameters = {
        "type": "object",
        "properties": {"path": {"type": "string"}},
        "required": ["path"],
    }

    async def execute(self, **kwargs):  # type: ignore[override]
        # TODO: 读取 Volume 文件
        return {"status": "ok", "path": kwargs.get("path"), "content": ""}


class ListFilesTool(BaseTool):
    name = "list_files"
    description = "列出目录内容。"
    parameters = {
        "type": "object",
        "properties": {"path": {"type": "string"}, "recursive": {"type": "boolean"}},
        "required": ["path"],
    }

    async def execute(self, **kwargs):  # type: ignore[override]
        # TODO: 列目录
        return {"status": "ok", "path": kwargs.get("path"), "files": []}


register(WriteFileTool())
register(ReadFileTool())
register(ListFilesTool())
