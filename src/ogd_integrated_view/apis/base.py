from typing import Any


class ApiDefinition:
    name: str
    base_url: str
    auth_type: str = "none"
    params: dict[str, Any] = {}

    def request_params(self) -> dict[str, Any]:
        return dict(self.params)

    def normalize(self, raw_response: Any) -> list[dict[str, Any]]:
        raise NotImplementedError
