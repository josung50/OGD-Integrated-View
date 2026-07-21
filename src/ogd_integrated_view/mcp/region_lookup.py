import json
from pathlib import Path

_LAWD_CODES_PATH = Path(__file__).parent / "data" / "lawd_codes.json"
_LAWD_CODES: list[dict[str, str]] = json.loads(_LAWD_CODES_PATH.read_text(encoding="utf-8"))


def _find_region_entry(text: str) -> dict[str, str] | None:
    """텍스트에서 시/군/구 이름을 찾아 가장 구체적인(이름이 긴) 항목을 반환한다.

    '수원시'와 '수원시 영통구'처럼 상위/하위 지역이 모두 등록된 경우, 더 구체적인
    (이름이 더 긴) 쪽을 우선한다.

    단어 경계 없는 부분열 포함 검사(`last_part in text`)는 쓰지 않는다 — "남구"가
    "강남구"의 부분열이라 "서울 강남구 ..."에서 엉뚱하게 "경상북도 포항시 남구"가
    (이름이 더 길다는 이유로) 우선 매칭되는 등, 서로 다른 지역의 구 이름이 겹치는
    사고가 난다. 주소는 공백으로 구분된 토큰이므로 토큰 단위로 정확히 일치하는지만 본다.
    """
    tokens = text.split()
    best: dict[str, str] | None = None
    for entry in _LAWD_CODES:
        last_part = entry["name"].split()[-1]
        if last_part in tokens and (best is None or len(entry["name"]) > len(best["name"])):
            best = entry
    return best


def find_region_code(text: str) -> str | None:
    """텍스트에서 시/군/구 이름을 찾아 5자리 법정동코드(LAWD_CD)를 반환한다."""
    entry = _find_region_entry(text)
    return entry["code"] if entry else None


def find_region_name(text: str) -> str | None:
    """텍스트에서 시/군/구 이름을 찾아 전체 지역명(예: '경기도 김포시')을 반환한다.

    도로명 주소만으로는 지오코딩이 다른 지역과 중복될 수 있어, 실거래가 항목의
    도로명 앞에 붙여줄 정확한 지역명이 필요할 때 사용한다.
    """
    entry = _find_region_entry(text)
    return entry["name"] if entry else None
