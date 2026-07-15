from typing import Any


class McpServerDefinition:
    name: str
    command: str | None = None
    args: list[str] = []
    url: str | None = None
    env: dict[str, str] = {}
    tool_name: str
    tool_arguments: dict[str, Any] = {}

    def build_arguments(self) -> dict[str, Any]:
        return dict(self.tool_arguments)
