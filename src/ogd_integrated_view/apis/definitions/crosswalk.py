import os
from typing import Any

from ogd_integrated_view.apis.base import ApiDefinition


class CrosswalkApi(ApiDefinition):
    """전국횡단보도표준데이터 (data.go.kr, tn_pubr_public_crosswalk_api)

    입지 분석에서 특정 지점 주변 학교까지 횡단보도를 건너지 않고 갈 수 있는지
    판정하는 백엔드 로직에서 사용할 원본 데이터.
    """

    name = "crosswalk"
    base_url = "https://api.data.go.kr/openapi/tn_pubr_public_crosswalk_api"
    auth_type = "api_key"
    params = {"pageNo": 1, "numOfRows": 1000, "type": "json"}

    def request_params(self) -> dict[str, Any]:
        params = dict(self.params)
        params["serviceKey"] = os.environ.get("PUBLIC_DATA_API_KEY", "")
        return params

    def normalize(self, raw_response: Any) -> list[dict[str, Any]]:
        items = raw_response.get("response", {}).get("body", {}).get("items", [])
        if isinstance(items, dict):
            items = items.get("item", [])
        if isinstance(items, dict):
            items = [items]
        return items
