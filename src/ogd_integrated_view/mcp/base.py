from typing import Any


class McpServerDefinition:
    name: str
    role: str | None = None
    command: str | None = None
    args: list[str] = []
    cwd: str | None = None
    url: str | None = None
    env: dict[str, str] = {}
    tool_name: str
    tool_arguments: dict[str, Any] = {}
    query_param: str | None = None

    def build_arguments(self, question: str | None = None) -> dict[str, Any]:
        args = dict(self.tool_arguments)
        if question is not None and self.query_param:
            args[self.query_param] = question
        return args

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "McpServerDefinition":
        obj = cls()
        obj.name = data["name"]
        obj.role = data.get("role")
        obj.command = data.get("command")
        obj.args = data.get("args", [])
        obj.cwd = data.get("cwd")
        obj.url = data.get("url")
        obj.env = data.get("env", {})
        obj.tool_name = data.get("tool_name", "")
        obj.tool_arguments = data.get("extra_arguments", {})
        obj.query_param = data.get("query_param")
        return obj
