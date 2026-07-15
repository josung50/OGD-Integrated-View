import importlib
import pkgutil

from ogd_integrated_view.mcp import definitions
from ogd_integrated_view.mcp.base import McpServerDefinition
from ogd_integrated_view.mcp.config_store import load_servers


def discover_mcp_servers() -> list[McpServerDefinition]:
    servers: list[McpServerDefinition] = []
    for _, module_name, _ in pkgutil.iter_modules(definitions.__path__):
        module = importlib.import_module(f"{definitions.__name__}.{module_name}")
        for attr in vars(module).values():
            if isinstance(attr, type) and issubclass(attr, McpServerDefinition) and attr is not McpServerDefinition:
                servers.append(attr())
    servers.extend(McpServerDefinition.from_dict(data) for data in load_servers())
    return servers


def find_server_by_role(role: str) -> McpServerDefinition | None:
    for server in discover_mcp_servers():
        if server.role == role:
            return server
    return None
