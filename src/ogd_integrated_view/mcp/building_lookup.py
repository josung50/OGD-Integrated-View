import os

import requests

KAKAO_ADDRESS_SEARCH_URL = "https://dapi.kakao.com/v2/local/search/address.json"
KAKAO_KEYWORD_SEARCH_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"


def find_building_name(road_address: str) -> str | None:
    """도로명주소로 건물명(아파트/빌라/오피스텔 단지명 등)을 조회한다.

    카카오 로컬 API의 주소 검색 결과 중 road_address.building_name을 사용한다.
    건물명이 등록되어 있지 않은 주소(일반 단독주택 등)면 None을 반환한다.
    """
    api_key = os.environ.get("KAKAO_API_KEY", "")
    if not api_key:
        raise RuntimeError("KAKAO_API_KEY가 설정되어 있지 않습니다.")

    response = requests.get(
        KAKAO_ADDRESS_SEARCH_URL,
        headers={"Authorization": f"KakaoAK {api_key}"},
        params={"query": road_address},
        timeout=10,
    )
    response.raise_for_status()
    documents = response.json().get("documents", [])
    if not documents:
        return None

    road_addr = documents[0].get("road_address") or {}
    building_name = (road_addr.get("building_name") or "").strip()
    return building_name or None


def resolve_address(query: str) -> str:
    """검색창 입력을 도로명주소로 정규화한다.

    입지분석에 쓰는 MCP 도구들은 대부분 네이버 지오코더(도로명/지번 주소만 인식)로
    좌표를 찾기 때문에, "은마아파트"처럼 단지명만 입력하면 실패한다. 카카오 키워드
    검색으로 먼저 실제 도로명주소를 찾아 치환해두면 이후 모든 조회가 이 주소를 쓰게 되어
    단지명 검색도 동작한다. 이미 정상 주소이거나 키워드 검색으로 못 찾으면 원본 그대로 반환한다.
    """
    api_key = os.environ.get("KAKAO_API_KEY", "")
    if not api_key:
        return query

    try:
        response = requests.get(
            KAKAO_KEYWORD_SEARCH_URL,
            headers={"Authorization": f"KakaoAK {api_key}"},
            params={"query": query},
            timeout=10,
        )
        response.raise_for_status()
        documents = response.json().get("documents", [])
    except requests.exceptions.RequestException:
        return query

    if not documents:
        return query

    road_address = documents[0].get("road_address_name") or documents[0].get("address_name")
    return road_address or query
