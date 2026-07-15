import json
from pathlib import Path
from typing import Any

CONFIG_PATH = Path("data/mcp_servers.json")


def load_servers() -> list[dict[str, Any]]:
    if not CONFIG_PATH.exists():
        return []
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def save_servers(servers: list[dict[str, Any]]) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(servers, ensure_ascii=False, indent=2), encoding="utf-8")
