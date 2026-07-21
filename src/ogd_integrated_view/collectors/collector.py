import asyncio
import time
from datetime import datetime, timezone
from typing import Any

import requests

from ogd_integrated_view.apis.base import ApiDefinition
from ogd_integrated_view.apis.registry import discover_api_definitions
from ogd_integrated_view.mcp.client import call_tool
from ogd_integrated_view.mcp.registry import discover_mcp_servers
from ogd_integrated_view.storage.repository import Repository

REQUEST_TIMEOUT_SECONDS = 30
MAX_RETRIES_PER_PAGE = 3
RETRY_BACKOFF_SECONDS = 3


def collect_all(repository: Repository) -> None:
    for api in discover_api_definitions():
        records = _fetch_api_records(api)
        _stamp_collected_at(records)
        repository.save(api.name, records)

    for server in discover_mcp_servers():
        result = asyncio.run(call_tool(server))
        record = {"collected_at": _now_iso(), "raw": _mcp_result_to_text(result)}
        repository.save(server.name, [record])


def refresh_api(name: str, repository: Repository) -> int:
    """이름으로 지정한 API 정의 하나만 다시 수집해 해당 시트를 최신 데이터로 통째로 교체한다.

    (수동 "최신화" 버튼처럼, 누적 append가 아니라 항상 최신 스냅샷으로 덮어써야 하는 경우용)
    반환값은 수집된 행 수.
    """
    api = next((a for a in discover_api_definitions() if a.name == name), None)
    if api is None:
        raise ValueError(f"등록된 API 정의를 찾을 수 없습니다: {name}")

    records = _fetch_api_records(api)
    _stamp_collected_at(records)
    repository.save(api.name, records, replace=True)
    return len(records)


def _fetch_api_records(api: ApiDefinition) -> list[dict]:
    """API 응답을 가져온다. params에 pageNo가 있으면 data.go.kr류 페이지네이션 규약
    (pageNo/numOfRows/totalCount)으로 간주해 totalCount에 도달할 때까지 계속 조회한다.
    """
    params = api.request_params()
    if "pageNo" not in params:
        response = _get_with_retry(api.base_url, params)
        return api.normalize(response.json())

    num_of_rows = int(params.get("numOfRows", 1000)) or 1000
    records: list[dict] = []
    page = 1
    total_pages: int | None = None
    failed_pages: list[int] = []

    while total_pages is None or page <= total_pages:
        params["pageNo"] = page
        try:
            response = _get_with_retry(api.base_url, params)
            raw = response.json()
        except requests.exceptions.RequestException as exc:
            print(f"[collector] {api.name}: page {page} 수집 실패, 건너뜀: {exc}", flush=True)
            failed_pages.append(page)
            page += 1
            continue

        page_records = api.normalize(raw)
        records.extend(page_records)
        total = _extract_total_count(raw)
        if total_pages is None:
            if total is not None:
                total_pages = max(1, -(-total // num_of_rows))
            elif not page_records:
                break
        page_label = f"{page}/{total_pages}" if total_pages else str(page)
        count_label = f"{len(records)}/{total}" if total is not None else str(len(records))
        print(f"[collector] {api.name}: page {page_label} 완료 ({count_label}건)", flush=True)
        page += 1

    if failed_pages:
        print(f"[collector] {api.name}: {len(failed_pages)}개 페이지 수집 실패 (건너뜀): {failed_pages}", flush=True)
    return records


def _get_with_retry(url: str, params: dict) -> requests.Response:
    last_error: Exception | None = None
    for attempt in range(1, MAX_RETRIES_PER_PAGE + 1):
        try:
            response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as exc:
            last_error = exc
            print(f"[collector] 요청 실패 ({attempt}/{MAX_RETRIES_PER_PAGE}): {exc}", flush=True)
            if attempt < MAX_RETRIES_PER_PAGE:
                time.sleep(RETRY_BACKOFF_SECONDS * attempt)
    raise last_error


def _extract_total_count(raw: Any) -> int | None:
    try:
        return int(raw["response"]["body"]["totalCount"])
    except (KeyError, TypeError, ValueError):
        return None


def _mcp_result_to_text(result: Any) -> str:
    content = getattr(result, "content", None)
    if not content:
        return str(result)
    parts = [getattr(item, "text", None) or str(item) for item in content]
    return "\n\n".join(parts)


def _stamp_collected_at(records: list[dict]) -> None:
    now = _now_iso()
    for record in records:
        record.setdefault("collected_at", now)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
