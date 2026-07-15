import os
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from ogd_integrated_view.mcp.base import McpServerDefinition


async def call_tool(definition: McpServerDefinition) -> Any:
    if definition.command is None:
        raise NotImplementedError("http/sse 방식 MCP 서버는 아직 미구현")

    env = {**os.environ, **{k: os.path.expandvars(v) for k, v in definition.env.items()}}
    params = StdioServerParameters(command=definition.command, args=definition.args, env=env)

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await session.call_tool(definition.tool_name, definition.build_arguments())
