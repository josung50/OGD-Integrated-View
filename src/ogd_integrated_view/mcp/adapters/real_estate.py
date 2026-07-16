import json
import re
from datetime import date
from typing import Any

from mcp import ClientSession
from mcp.client.stdio import stdio_client

from ogd_integrated_view.mcp.base import McpServerDefinition
from ogd_integrated_view.mcp.client import build_stdio_params

TRADE_TOOL_BY_KEYWORD = {
    "아파트": "get_apartment_trades",
    "오피스텔": "get_officetel_trades",
    "연립": "get_villa_trades",
    "다세대": "get_villa_trades",
    "단독": "get_single_house_trades",
    "다가구": "get_single_house_trades",
    "상업": "get_commercial_trade",
}
DEFAULT_TRADE_TOOL = "get_apartment_trades"

# 매물 유형/의도를 나타내는 표현. 지역도, 매물명(아파트명 등)도 아닌 "잡음" 취급해서 버린다.
INTENT_KEYWORDS = [
    *TRADE_TOOL_BY_KEYWORD.keys(),
    "연립다세대",
    "단독다가구",
    "매매",
    "전세",
    "월세",
    "전월세",
    "실거래가",
    "실거래",
    "시세",
    "가격",
    "알려줘",
    "알려주세요",
    "확인",
    "조회",
    "검색",
    "정보",
]

# get_region_code는 법정동(시/군/구/읍/면/동/리) 단위 이름만 인식한다. 도로명·건물명은 인식하지
# 못하므로, 이 접미사로 끝나는 토큰만 지역 후보로 보고 나머지는 매물명 후보로 남겨둔다.
ADMIN_SUFFIXES = ("특별시", "광역시", "특별자치시", "특별자치도", "시", "군", "구", "읍", "면", "동", "리")
KNOWN_SIDO = {
    "서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종",
    "경기", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주",
}


def _pick_trade_tool(question: str) -> str:
    for keyword, tool in TRADE_TOOL_BY_KEYWORD.items():
        if keyword in question:
            return tool
    return DEFAULT_TRADE_TOOL


def _extract_year_month(question: str) -> str:
    match = re.search(r"(20\d{2})[.\-년/\s]?(\d{1,2})월?", question)
    if match:
        return f"{match.group(1)}{int(match.group(2)):02d}"
    today = date.today()
    return f"{today.year}{today.month:02d}"


def _classify_tokens(question: str) -> tuple[list[str], list[str]]:
    """질문을 (지역 후보 토큰들, 매물명 후보 토큰들)로 나눈다."""
    cleaned = re.sub(r"(20\d{2})[.\-년/\s]?(\d{1,2})월?", " ", question)
    region_tokens: list[str] = []
    other_tokens: list[str] = []
    for raw_token in cleaned.split():
        token = raw_token.strip(",.!?()")
        if not token:
            continue
        if token in KNOWN_SIDO or token.endswith(ADMIN_SUFFIXES):
            region_tokens.append(token)
        elif any(keyword in token for keyword in INTENT_KEYWORDS):
            continue
        else:
            other_tokens.append(token)
    return region_tokens, other_tokens


def _text(result: Any) -> str:
    content = getattr(result, "content", None) or []
    return "\n".join(getattr(item, "text", None) or str(item) for item in content)


def _filter_by_name(payload: dict[str, Any], name_hints: list[str]) -> tuple[dict[str, Any], str | None]:
    items = payload.get("items")
    if not name_hints or not isinstance(items, list):
        return payload, None

    matched = [item for item in items if any(hint in item.get("apt_name", "") for hint in name_hints)]
    hint_text = " ".join(name_hints)
    if matched:
        filtered = {**payload, "items": matched, "total_count": len(matched)}
        return filtered, f"'{hint_text}' 이름이 포함된 {len(matched)}건으로 필터링했습니다."
    return payload, f"'{hint_text}'와 일치하는 이름이 없어 전체 결과를 보여드립니다."


async def query(server: McpServerDefinition, question: str) -> str:
    """지역명을 코드로 변환(get_region_code)한 뒤 실거래가 조회 tool을 자동으로 이어 호출한다.

    도로명 주소는 국토교통부 실거래가 API 자체가 지원하지 않아 지역 인식에 쓸 수 없다.
    대신 시/군/구/동 등 법정동 단위로 지역을 찾고, 나머지 단어(아파트명 등)는 조회 결과를
    받아온 뒤 클라이언트 쪽에서 이름으로 필터링한다.
    """
    params = build_stdio_params(server)

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            region_tokens, other_tokens = _classify_tokens(question)
            region_query = " ".join(region_tokens) if region_tokens else question
            region_text = _text(await session.call_tool("get_region_code", {"query": region_query}))
            try:
                region_data = json.loads(region_text)
            except json.JSONDecodeError:
                return f"지역 코드를 확인하지 못했습니다.\n\n{region_text}"

            region_code = region_data.get("region_code")
            full_name = region_data.get("full_name", region_query)
            if not region_code:
                if not region_tokens:
                    return (
                        f"'{question}'에서 시/군/구 정보를 찾지 못했습니다.\n\n"
                        "도로명 주소나 아파트명만으로는 검색할 수 없어요 "
                        "(국토교통부 실거래가 API가 법정동 단위로만 데이터를 제공합니다). "
                        "'강남구', '강남구 역삼동'처럼 시/군/구를 함께 입력해주세요."
                    )
                return f"'{region_query}'에서 지역을 찾지 못했습니다.\n\n{region_text}"

            trade_tool = _pick_trade_tool(question)
            year_month = _extract_year_month(question)
            trade_text = _text(
                await session.call_tool(
                    trade_tool, {"region_code": region_code, "year_month": year_month}
                )
            )

            header = f"[{full_name} / {year_month} / {trade_tool}]"
            try:
                payload = json.loads(trade_text)
            except json.JSONDecodeError:
                return f"{header}\n\n{trade_text}"

            payload, filter_note = _filter_by_name(payload, other_tokens)
            if filter_note:
                header += f"\n{filter_note}"
            return f"{header}\n\n{json.dumps(payload, ensure_ascii=False, indent=2)}"
