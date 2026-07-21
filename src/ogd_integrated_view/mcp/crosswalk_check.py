import math
from typing import Any

import pandas as pd

from ogd_integrated_view.storage.repository import Repository

CROSSWALK_BUFFER_M = 20.0
"""직선 경로에서 이 거리(m) 이내에 횡단보도가 있으면 '건너야 함'으로 판정.

실제 보행자 도로망 경로 데이터가 없어, 출발지-도착지를 잇는 직선 경로 근처에
횡단보도가 있는지로 근사한다 (완전히 정확한 판정은 아니며 참고용).
"""


_crosswalk_cache: pd.DataFrame | None = None


def load_crosswalks(force_reload: bool = False) -> pd.DataFrame:
    """crosswalk 시트를 불러온다. 5만 행짜리 엑셀 시트를 매번 새로 읽으면 요청당 10초 넘게
    걸려서, 프로세스 안에서는 한 번만 읽고 메모리에 캐싱해 재사용한다.
    데이터를 새로 수집(최신화)한 뒤에는 force_reload=True로 캐시를 갱신해야 한다.
    """
    global _crosswalk_cache
    if _crosswalk_cache is None or force_reload:
        df = Repository().load("crosswalk")
        if not df.empty:
            df = df.copy()
            df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
            df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
            df = df.dropna(subset=["latitude", "longitude"])
        _crosswalk_cache = df
    return _crosswalk_cache


def check_crosswalk_crossing(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
    crosswalks: pd.DataFrame | None = None,
) -> dict[str, Any]:
    """origin에서 dest까지 직선 경로 근처(기본 20m 이내)에 횡단보도가 있는지 판정한다."""
    if crosswalks is None:
        crosswalks = load_crosswalks()
    if crosswalks.empty:
        return {"crossing_required": None, "message": "횡단보도 데이터가 수집되어 있지 않습니다.", "matched": []}

    margin = 0.01  # 위경도 약 0.01도 ~ 1.1km 여유를 두고 후보를 추린다
    lat_min, lat_max = min(origin_lat, dest_lat) - margin, max(origin_lat, dest_lat) + margin
    lon_min, lon_max = min(origin_lon, dest_lon) - margin, max(origin_lon, dest_lon) + margin
    candidates = crosswalks[
        crosswalks["latitude"].between(lat_min, lat_max) & crosswalks["longitude"].between(lon_min, lon_max)
    ]
    if candidates.empty:
        return {"crossing_required": False, "message": "경로 주변에서 횡단보도를 찾지 못했습니다.", "matched": []}

    ox, oy = _to_xy(origin_lat, origin_lon, origin_lat)
    dx, dy = _to_xy(dest_lat, dest_lon, origin_lat)

    matched = []
    for _, row in candidates.iterrows():
        px, py = _to_xy(row["latitude"], row["longitude"], origin_lat)
        distance_m = _point_segment_distance_m(px, py, ox, oy, dx, dy)
        if distance_m <= CROSSWALK_BUFFER_M:
            matched.append(
                {
                    "road_name": row.get("roadNm", ""),
                    "address": row.get("lnmadr", ""),
                    "distance_from_path_m": round(distance_m, 1),
                    "pedestrian_signal": row.get("tfclghtYn", ""),
                    "management_no": row.get("crslkManageNo", ""),
                }
            )
    matched.sort(key=lambda m: m["distance_from_path_m"])

    crossing_required = len(matched) > 0
    message = (
        f"경로상 약 {matched[0]['distance_from_path_m']}m 지점에 횡단보도가 있어 건너야 할 가능성이 높습니다."
        if crossing_required
        else "직선 경로 기준으로는 횡단보도가 확인되지 않았습니다."
    )
    return {"crossing_required": crossing_required, "message": message, "matched": matched[:5]}


def _to_xy(lat: float, lon: float, origin_lat: float) -> tuple[float, float]:
    """위경도를 origin_lat 기준 평면(미터) 좌표로 근사 변환 (등장방형 도법)."""
    m_per_deg_lat = 111_320.0
    m_per_deg_lon = 111_320.0 * math.cos(math.radians(origin_lat))
    return lon * m_per_deg_lon, lat * m_per_deg_lat


def _point_segment_distance_m(px: float, py: float, ax: float, ay: float, bx: float, by: float) -> float:
    abx, aby = bx - ax, by - ay
    length_sq = abx * abx + aby * aby
    if length_sq == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * abx + (py - ay) * aby) / length_sq))
    proj_x, proj_y = ax + t * abx, ay + t * aby
    return math.hypot(px - proj_x, py - proj_y)
