import importlib
import pkgutil

from ogd_integrated_view.mcp import definitions
from ogd_integrated_view.mcp.base import McpServerDefinition


def discover_mcp_servers() -> list[McpServerDefinition]:
    servers: list[McpServerDefinition] = []
    for _, module_name, _ in pkgutil.iter_modules(definitions.__path__):
        module = importlib.import_module(f"{definitions.__name__}.{module_name}")
        for attr in vars(module).values():
            if isinstance(attr, type) and issubclass(attr, McpServerDefinition) and attr is not McpServerDefinition:
                servers.append(attr())
    return servers
