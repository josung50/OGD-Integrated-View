import os
from datetime import date
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from ogd_integrated_view.mcp.base import McpServerDefinition


def months_ago(months: int, today: date | None = None) -> str:
    today = today or date.today()
    total = today.year * 12 + (today.month - 1) - months
    year, month = divmod(total, 12)
    return f"{year}{month + 1:02d}"


def build_stdio_params(definition: McpServerDefinition) -> StdioServerParameters:
    if definition.command is None:
        raise NotImplementedError("http/sse 방식 MCP 서버는 아직 미구현")

    env = {
        **os.environ,
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUTF8": "1",
        **{k: os.path.expandvars(v) for k, v in definition.env.items()},
    }
    return StdioServerParameters(
        command=definition.command,
        args=definition.args,
        env=env,
        cwd=definition.cwd,
        encoding="utf-8",
    )


async def call_tool(definition: McpServerDefinition, question: str | None = None) -> Any:
    params = build_stdio_params(definition)

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await session.call_tool(definition.tool_name, definition.build_arguments(question))
