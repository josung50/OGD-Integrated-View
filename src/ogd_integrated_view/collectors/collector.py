from ogd_integrated_view.apis.registry import discover_api_definitions
from ogd_integrated_view.mcp.registry import discover_mcp_servers
from ogd_integrated_view.storage.repository import Repository


def collect_all(repository: Repository) -> None:
    for api in discover_api_definitions():
        raise NotImplementedError

    for server in discover_mcp_servers():
        raise NotImplementedError
