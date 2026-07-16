import json
from pathlib import Path
from typing import Any

CONFIG_PATH = Path("data/mcp_servers.json")
APP_SETTINGS_PATH = Path("data/app_settings.json")


def load_servers() -> list[dict[str, Any]]:
    if not CONFIG_PATH.exists():
        return []
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def save_servers(servers: list[dict[str, Any]]) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(servers, ensure_ascii=False, indent=2), encoding="utf-8")


def load_app_settings() -> dict[str, Any]:
    if not APP_SETTINGS_PATH.exists():
        return {}
    return json.loads(APP_SETTINGS_PATH.read_text(encoding="utf-8"))


def save_app_settings(settings: dict[str, Any]) -> None:
    APP_SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    APP_SETTINGS_PATH.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")
