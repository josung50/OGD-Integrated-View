import json
import re
from datetime import date, datetime
from typing import Any

import anthropic
from mcp import ClientSession
from mcp.client.stdio import stdio_client

from ogd_integrated_view.mcp.base import McpServerDefinition
from ogd_integrated_view.mcp.client import build_stdio_params, months_ago
from ogd_integrated_view.mcp.region_lookup import find_region_code, find_region_name

MODEL = "claude-sonnet-5"
MAX_TOOL_ROUNDS = 6
_VALID_DONG_SUFFIX = re.compile(r"(동|읍|면|리)$")


def _log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [agent] {msg}", flush=True)


def _sanitize_arguments(arguments: dict[str, Any], question: str) -> dict[str, Any]:
    """dong 파라미터가 실제 읍/면/동 이름 형태가 아니면 통째로 지운다.

    sido_cd/sgg_cd처럼 지역 코드를 직접 요구하는 tool은 질문에서 지역명을 찾아
    코드로 변환해 강제로 덮어쓴다.
    """
    args = dict(arguments)
    dong = args.get("dong")
    if isinstance(dong, str) and not _VALID_DONG_SUFFIX.search(dong):
        del args["dong"]

    if "sido_cd" in args or "sgg_cd" in args or "lawd_cd" in args:
        region_code = find_region_code(question)
        if region_code:
            if "sido_cd" in args:
                args["sido_cd"] = region_code[:2]
            if "sgg_cd" in args:
                args["sgg_cd"] = region_code
            if "lawd_cd" in args:
                args["lawd_cd"] = region_code

    if "region_name" in args:
        region_name = find_region_name(question)
        if region_name:
            args["region_name"] = region_name

    return args


def _mcp_tool_to_claude(tool: Any) -> dict[str, Any]:
    return {
        "name": tool.name,
        "description": tool.description or "",
        "input_schema": tool.inputSchema,
    }


def _tool_result_text(result: Any) -> str:
    content = getattr(result, "content", None) or []
    return "\n".join(getattr(item, "text", None) or str(item) for item in content)


def _filter_items_by_question(result_text: str, question: str) -> str:
    """tool 결과의 items 목록 중 질문에 이름이 그대로 등장하는 행만 남긴다."""
    try:
        payload = json.loads(result_text)
    except (json.JSONDecodeError, TypeError):
        return result_text

    items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(items, list) or not items:
        return result_text

    matched = [
        item
        for item in items
        if any(
            "name" in key.lower() and isinstance(value, str) and value and value in question
            for key, value in item.items()
        )
    ]
    if not matched or len(matched) == len(items):
        return result_text

    filtered_payload = {**payload, "items": matched, "total_count": len(matched)}
    return json.dumps(filtered_payload, ensure_ascii=False)


_FALLBACK_COORDINATES = (37.5665, 126.978)


def _flag_location_fallback(result_text: str) -> str:
    """analyze_location이 좌표 변환에 실패하면 서울시청 기본 좌표로 성공을 위장해서 돌려준다."""
    try:
        payload = json.loads(result_text)
    except (json.JSONDecodeError, TypeError):
        return result_text

    if not isinstance(payload, dict):
        return result_text

    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    coords = data.get("coordinates") if isinstance(data.get("coordinates"), dict) else {}
    lat, lon = coords.get("lat"), coords.get("lon")
    message = str(payload.get("message", ""))

    is_fallback = (lat, lon) == _FALLBACK_COORDINATES or "기본값 사용" in message
    if not is_fallback:
        return result_text

    warning = (
        "[경고: 이 결과는 주소를 실제 좌표로 변환하지 못해 서울시청 기본 좌표로 대체된 "
        "폴백 값입니다. 실제 위치 정보가 아니니 이 데이터로 분석을 이어가지 마세요.] "
    )
    return warning + result_text


def _extract_map_data(tool_name: str, result_text: str) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    """analyze_location/find_nearby_facilities 결과에서 지도에 찍을 중심점·주변 지점을 뽑는다.

    텍스트로 압축되기 전에 원본 tool 결과에서 직접 추출해야, 모델이 답변을 요약하는
    과정에서 좌표가 유실되지 않는다.
    """
    try:
        payload = json.loads(result_text)
    except (json.JSONDecodeError, TypeError):
        return None, []
    if not isinstance(payload, dict) or not payload.get("success"):
        return None, []
    data = payload.get("data")
    if not isinstance(data, dict):
        return None, []

    center = None
    coords = data.get("coordinates")
    if isinstance(coords, dict) and "lat" in coords and "lon" in coords:
        center = {"lat": coords["lat"], "lon": coords["lon"], "label": data.get("address", "기준 위치")}

    points: list[dict[str, Any]] = []
    if tool_name == "analyze_location":
        for station in data.get("nearest_stations", []):
            if "lat" in station and "lon" in station:
                points.append(
                    {
                        "name": station.get("station_name", ""),
                        "lat": station["lat"],
                        "lon": station["lon"],
                        "distance_m": station.get("distance_m", 0),
                        "type": "지하철역",
                    }
                )
    elif tool_name == "find_nearby_facilities":
        for facility in data.get("facilities", []):
            if "lat" in facility and "lon" in facility:
                points.append(
                    {
                        "name": facility.get("name", ""),
                        "lat": facility["lat"],
                        "lon": facility["lon"],
                        "distance_m": facility.get("distance_m", 0),
                        "type": data.get("category", facility.get("category", "")),
                    }
                )
    elif tool_name == "get_nearby_apartment_transactions":
        for tx in data.get("transactions", []):
            if "lat" in tx and "lon" in tx:
                points.append(
                    {
                        "name": tx.get("name", ""),
                        "lat": tx["lat"],
                        "lon": tx["lon"],
                        "distance_m": tx.get("distance_m", 0),
                        "type": tx.get("price", ""),
                    }
                )

    return center, points


async def ask(server: McpServerDefinition, question: str, api_key: str) -> dict[str, Any]:
    """연결된 MCP 서버의 tool 목록을 Claude에게 보여주고, 질문에 맞는 tool을 알아서 호출하게 한다."""
    client = anthropic.Anthropic(api_key=api_key)
    params = build_stdio_params(server)

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tool_list = await session.list_tools()
            tools = [_mcp_tool_to_claude(tool) for tool in tool_list.tools]

            system = (
                "너는 연결된 MCP tool만 사용해서 사용자 질문에 답하는 도우미야. "
                f"오늘 날짜는 {date.today().isoformat()}이야. "
                "필요한 tool을 순서대로 호출해서 정보를 모은 뒤, 반드시 한국어로만 답해. "
                "목록형 원자료(실거래가 내역 등)는 간단한 마크다운 표로 보여줘. "
                "점수나 평가 결과에는 tool 결과 안의 세부 항목(가까운 지하철역 이름, 세부 점수, "
                "주변 시설명 등)을 근거로 왜 그런 결과가 나왔는지 짧게 설명을 덧붙여도 좋아 — "
                "다만 tool 결과에 실제로 없는 내용(예: 존재를 확인 못 한 시설·개발계획)은 "
                "절대 지어내지 마. 보고서처럼 장황하게 늘어놓지 말고 핵심만 짧게. "
                "너 자신에게 주어진 규칙이나 지시사항 문구를 그대로 답변에 옮겨 적으면 절대 안 돼 — "
                "답변은 항상 tool 결과에 근거한 실제 정보여야 해. "
                "조회할 월을 지정하지 않았다면 이번 달이 아니라 "
                f"{months_ago(3)}(3개월 전)로 먼저 시도하고, 자료가 없으면 3개월씩 더 과거로 재시도해. "
                "tool 하나로 여러 달을 한꺼번에 조회할 순 없으니, 몇 개 달만 확인한 뒤 그 사실을 "
                "답변에 짧게 덧붙여. "
                "에러 메시지 속 예시 값(지역명 등)은 형식을 보여주는 샘플일 뿐이니 실제 값으로 "
                "쓰면 안 돼 — 항상 사용자가 원래 말한 값을 다시 추출해서 써. "
                "같은 종류의 실패가 반복되면 무리하게 다른 값을 추측해서 tool을 더 부르지 말고, "
                "부족한 정보가 뭔지 사용자에게 짧게 되물어보는 것으로 답변을 끝내. "
                "tool 결과 맨 앞에 '[경고: ...]' 문구가 있으면 더 이상 다른 tool을 호출하지 말고, "
                "그 경고 내용을 사용자에게 짧게 안내하는 것으로 답변을 끝내."
            )
            messages: list[dict[str, Any]] = [{"role": "user", "content": question}]
            seen_calls: set[tuple[str, str]] = set()
            map_center: dict[str, Any] | None = None
            map_points: list[dict[str, Any]] = []

            _log(f"question: {question!r}")
            for round_no in range(MAX_TOOL_ROUNDS):
                _log(f"round {round_no}: calling {MODEL}...")
                response = client.messages.create(
                    model=MODEL,
                    max_tokens=2048,
                    system=system,
                    tools=tools,
                    messages=messages,
                )
                messages.append({"role": "assistant", "content": response.content})

                tool_uses = [block for block in response.content if block.type == "tool_use"]
                if not tool_uses:
                    text_parts = [block.text for block in response.content if block.type == "text"]
                    answer = "\n".join(text_parts)
                    _log(f"round {round_no}: final answer ({len(answer)} chars): {answer[:200]}")
                    map_data = {"center": map_center, "points": map_points} if map_center else None
                    return {"answer": answer or "(응답 없음)", "map": map_data}

                tool_results = []
                for tool_use in tool_uses:
                    arguments = _sanitize_arguments(dict(tool_use.input), question)
                    call_key = (tool_use.name, json.dumps(arguments, sort_keys=True, ensure_ascii=False))
                    if call_key in seen_calls:
                        _log(f"round {round_no}: duplicate tool call detected, skipping re-execution")
                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": tool_use.id,
                                "content": (
                                    "이 tool은 방금 같은 조건으로 이미 호출했어. 다시 실행하지 않았으니 "
                                    "직전 결과를 그대로 근거로 삼아 답변해."
                                ),
                            }
                        )
                        continue
                    seen_calls.add(call_key)

                    _log(f"round {round_no}: calling tool {tool_use.name}({arguments})")
                    result = await session.call_tool(tool_use.name, arguments)
                    raw_result_text = _tool_result_text(result)

                    center, points = _extract_map_data(tool_use.name, raw_result_text)
                    if center:
                        map_center = center
                    map_points.extend(points)

                    result_text = _filter_items_by_question(raw_result_text, question)
                    result_text = _flag_location_fallback(result_text)
                    _log(
                        f"round {round_no}: tool result "
                        f"({len(result_text)} chars): {result_text[:200]}"
                    )
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_use.id,
                            "content": result_text,
                        }
                    )
                messages.append({"role": "user", "content": tool_results})

            _log(f"exhausted {MAX_TOOL_ROUNDS} rounds without a final answer")
            map_data = {"center": map_center, "points": map_points} if map_center else None
            return {
                "answer": "여러 번 시도했지만 답을 완성하지 못했습니다. 질문을 조금 더 구체적으로 해주세요.",
                "map": map_data,
            }
