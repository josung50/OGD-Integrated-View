import json
from typing import Any

from mcp import ClientSession
from mcp.client.stdio import stdio_client

from ogd_integrated_view.mcp.base import McpServerDefinition
from ogd_integrated_view.mcp.client import build_stdio_params
from ogd_integrated_view.mcp.region_lookup import find_region_code, find_region_name

CONVENIENCE_CATEGORIES = ["편의점", "카페", "은행", "약국"]
INFRA_CATEGORIES = ["대학병원", "대형마트"]
MAX_POINTS_PER_CATEGORY = 15


def _tool_result_json(result: Any) -> dict[str, Any] | None:
    content = getattr(result, "content", None) or []
    text = "\n".join(getattr(item, "text", None) or str(item) for item in content)
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None


async def analyze_all(server: McpServerDefinition, address: str, radius_km: float) -> dict[str, Any]:
    """지정한 주소 반경 내 지하철역/편의시설/주요 인프라/아파트 실거래를 한 번에 조회한다.

    LLM에게 어떤 tool을 부를지 맡기지 않고 항상 같은 4가지 조회를 고정 순서로 실행한다 —
    작은 로컬 모델이 tool 이름을 헷갈리거나 매 라운드마다 몇십 초씩 걸리는 문제를 피하기 위해서다.
    """
    lawd_cd = find_region_code(address)
    region_name = find_region_name(address)
    radius_m = int(radius_km * 1000)

    params = build_stdio_params(server)
    categories: dict[str, list[dict[str, Any]]] = {
        "subway": [],
        "convenience": [],
        "infra": [],
        "transactions": [],
    }
    center: dict[str, Any] | None = None
    errors: dict[str, str] = {}

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            loc_result = await session.call_tool("analyze_location", {"address": address})
            loc_data = _tool_result_json(loc_result)
            if loc_data and loc_data.get("success"):
                data = loc_data["data"]
                coords = data.get("coordinates", {})
                if "lat" in coords and "lon" in coords:
                    center = {"lat": coords["lat"], "lon": coords["lon"], "label": address}
                for station in data.get("nearest_stations", []):
                    if station.get("distance_km", 999) <= radius_km and "lat" in station:
                        categories["subway"].append(
                            {
                                "name": station.get("station_name", ""),
                                "lat": station["lat"],
                                "lon": station["lon"],
                                "distance_m": station.get("distance_m", 0),
                                "detail": ", ".join(station.get("lines", [])),
                            }
                        )
            else:
                errors["subway"] = (loc_data or {}).get("message", "위치 분석에 실패했습니다")

            for cat_key, kakao_categories in (
                ("convenience", CONVENIENCE_CATEGORIES),
                ("infra", INFRA_CATEGORIES),
            ):
                for kakao_cat in kakao_categories:
                    fac_result = await session.call_tool(
                        "find_nearby_facilities",
                        {"address": address, "category": kakao_cat, "radius": radius_m},
                    )
                    fac_data = _tool_result_json(fac_result)
                    if fac_data and fac_data.get("success"):
                        for fac in fac_data["data"].get("facilities", []):
                            if "lat" in fac and "lon" in fac:
                                categories[cat_key].append(
                                    {
                                        "name": fac.get("name", ""),
                                        "lat": fac["lat"],
                                        "lon": fac["lon"],
                                        "distance_m": fac.get("distance_m", 0),
                                        "detail": fac.get("category", kakao_cat),
                                    }
                                )
                    elif not fac_data or not fac_data.get("success"):
                        errors.setdefault(cat_key, (fac_data or {}).get("message", "편의시설 조회에 실패했습니다"))

            if center and lawd_cd and region_name:
                tx_result = await session.call_tool(
                    "get_nearby_apartment_transactions",
                    {
                        "address": address,
                        "lawd_cd": lawd_cd,
                        "region_name": region_name,
                        "radius_km": radius_km,
                        "months": 3,
                    },
                )
                tx_data = _tool_result_json(tx_result)
                if tx_data and tx_data.get("success"):
                    for tx in tx_data["data"].get("transactions", []):
                        if "lat" in tx and "lon" in tx:
                            categories["transactions"].append(
                                {
                                    "name": tx.get("name", ""),
                                    "lat": tx["lat"],
                                    "lon": tx["lon"],
                                    "distance_m": tx.get("distance_m", 0),
                                    "detail": tx.get("price", ""),
                                }
                            )
                else:
                    errors["transactions"] = (tx_data or {}).get("message", "실거래가 조회에 실패했습니다")
            else:
                errors["transactions"] = "주소에서 지역(시/군/구)을 인식하지 못해 실거래가를 조회할 수 없습니다"

    for points in categories.values():
        points.sort(key=lambda p: p.get("distance_m", 0))
        del points[MAX_POINTS_PER_CATEGORY:]

    return {"center": center, "categories": categories, "errors": errors}
