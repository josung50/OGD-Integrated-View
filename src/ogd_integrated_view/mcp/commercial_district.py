import os

import requests

STORE_LIST_IN_RADIUS_URL = "https://apis.data.go.kr/B553077/api/open/sdsc2/storeListInRadius"
REQUEST_TIMEOUT_SECONDS = 15

# 반경 조회는 상권이 밀집된 지역(강남 등)이면 1km 안에도 1만 건 넘게 나올 수 있어,
# 매 조회마다 전부 받아오면 느리고 대부분 쓸모없다. 상권 발달 정도 판단에는
# total_count(전체 개수)만으로도 충분하고, 업종 구성을 보고 싶을 때만 이 한도까지 받아온다.
DEFAULT_MAX_ROWS = 1000


def fetch_nearby_stores(lat: float, lon: float, radius_m: int, max_rows: int = DEFAULT_MAX_ROWS) -> dict:
    """반경 내 상가업소 정보를 조회한다 (소상공인시장진흥공단 상가(상권)정보 API).

    반환값의 total_count가 반경 내 전체 상가 수(상권 발달 정도의 기본 지표)이고,
    stores는 max_rows개까지의 개별 상가 목록이다 (업종 구성 분석 등에 사용).
    """
    api_key = os.environ.get("PUBLIC_DATA_API_KEY", "")
    if not api_key:
        raise RuntimeError("PUBLIC_DATA_API_KEY가 설정되어 있지 않습니다.")

    response = requests.get(
        STORE_LIST_IN_RADIUS_URL,
        params={
            "serviceKey": api_key,
            "cx": lon,
            "cy": lat,
            "radius": radius_m,
            "type": "json",
            "numOfRows": max_rows,
            "pageNo": 1,
        },
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    payload = response.json()

    header = payload.get("header", {})
    if header.get("resultCode") != "00":
        raise RuntimeError(f"상권정보 API 오류: {header.get('resultMsg', '알 수 없는 오류')}")

    body = payload.get("body", {})
    items = body.get("items", [])

    stores = [
        {
            "name": item.get("bizesNm", ""),
            "branch_name": item.get("brchNm", ""),
            "category_large": item.get("indsLclsNm", ""),
            "category_medium": item.get("indsMclsNm", ""),
            "category_small": item.get("indsSclsNm", ""),
            "road_address": item.get("rdnmAdr", ""),
            "lot_address": item.get("lnoAdr", ""),
            "lat": item.get("lat"),
            "lon": item.get("lon"),
        }
        for item in items
    ]

    return {
        "total_count": body.get("totalCount", len(stores)),
        "stores": stores,
    }


def summarize_by_category(stores: list[dict]) -> list[dict]:
    """업종대분류별 개수를 많은 순으로 집계한다 (상권 구성 파악용)."""
    counts: dict[str, int] = {}
    for store in stores:
        category = store.get("category_large") or "미분류"
        counts[category] = counts.get(category, 0) + 1
    return [
        {"category": category, "count": count}
        for category, count in sorted(counts.items(), key=lambda pair: pair[1], reverse=True)
    ]
