import json
from typing import Any

import streamlit as st

from ogd_integrated_view.mcp.config_store import load_app_settings

_MAP_COUNTER_KEY = "_kakao_map_counter"

CATEGORY_META: dict[str, dict[str, str]] = {
    "subway": {"label": "지하철역", "icon": "🚇", "color": "#4285F4"},
    "convenience": {"label": "편의시설", "icon": "🏪", "color": "#34A853"},
    "infra": {"label": "주요 인프라", "icon": "🏥", "color": "#EA4335"},
    "transactions": {"label": "아파트 실거래", "icon": "🏢", "color": "#A142F4"},
}


def render_kakao_map(
    center: dict[str, Any] | None,
    categories: dict[str, dict[str, Any]],
    focused_point: dict[str, Any] | None = None,
) -> None:
    """중심 위치와 카테고리별 주변 지점을 카카오맵에 색상별 마커+거리선으로 그린다.

    categories는 {키: {"meta": {"label", "icon", "color"}, "points": [...]}} 형태여야 한다 —
    호출부가 어떤 카테고리를 어떤 색으로 보여줄지 직접 정하도록, 이 함수는 특정 카테고리
    이름을 알지 못한다 (채팅 흐름의 단일 결과든, 대시보드의 4분류든 그대로 재사용 가능).

    focused_point(lat/lon/label)를 주면 지도가 전체 지점을 다 보여주는 대신 그 지점으로
    이동·확대된다 — 목록에서 특정 항목을 골랐을 때 그 위치로 바로 찾아가는 용도.
    """
    js_key = load_app_settings().get("kakao_js_key")
    if not js_key:
        st.info(
            "지도를 보려면 설정 탭에서 카카오 JavaScript 키(KAKAO_JS_KEY)를 등록하세요. "
            "(REST API 키와는 별도의 키입니다.)"
        )
        return
    if not center:
        return

    categories = {key: group for key, group in categories.items() if group.get("points")}
    if not categories:
        return

    st.session_state[_MAP_COUNTER_KEY] = st.session_state.get(_MAP_COUNTER_KEY, 0) + 1
    element_id = f"kakao-map-{st.session_state[_MAP_COUNTER_KEY]}"

    center_json = json.dumps(center, ensure_ascii=False)
    categories_json = json.dumps(categories, ensure_ascii=False)
    focused_point_json = json.dumps(focused_point, ensure_ascii=False)

    html = f"""
    <div id="{element_id}" style="width:100%;height:600px;border-radius:8px;"></div>
    <script src="https://dapi.kakao.com/v2/maps/sdk.js?appkey={js_key}&autoload=false"></script>
    <script>
    kakao.maps.load(function () {{
        var center = {center_json};
        var categories = {categories_json};
        var focusedPoint = {focused_point_json};
        var container = document.getElementById('{element_id}');
        var map = new kakao.maps.Map(container, {{
            center: new kakao.maps.LatLng(center.lat, center.lon),
            level: 5,
        }});

        var bounds = new kakao.maps.LatLngBounds();
        var centerPos = new kakao.maps.LatLng(center.lat, center.lon);
        bounds.extend(centerPos);

        var centerMarker = new kakao.maps.Marker({{
            position: centerPos,
            map: map,
            image: new kakao.maps.MarkerImage(
                'https://t1.daumcdn.net/mapjsapi/images/marker.png',
                new kakao.maps.Size(29, 42)
            ),
        }});
        var centerInfo = new kakao.maps.InfoWindow({{
            content: '<div style="padding:6px 10px;font-size:13px;font-weight:bold;">' + center.label + '</div>',
        }});
        centerInfo.open(map, centerMarker);

        var focusedOverlay = null;

        Object.keys(categories).forEach(function (key) {{
            var group = categories[key];
            var color = group.meta.color;

            group.points.forEach(function (point) {{
                var pos = new kakao.maps.LatLng(point.lat, point.lon);
                bounds.extend(pos);

                var isFocused = focusedPoint && focusedPoint.lat === point.lat && focusedPoint.lon === point.lon;

                var dot = document.createElement('div');
                dot.style.width = isFocused ? '20px' : '14px';
                dot.style.height = isFocused ? '20px' : '14px';
                dot.style.borderRadius = '50%';
                dot.style.background = color;
                dot.style.border = isFocused ? '3px solid #FFD700' : '2px solid #fff';
                dot.style.boxShadow = isFocused ? '0 0 8px rgba(0,0,0,0.7)' : '0 0 3px rgba(0,0,0,0.5)';

                var overlay = new kakao.maps.CustomOverlay({{
                    position: pos,
                    content: dot,
                    map: map,
                    zIndex: isFocused ? 100 : 1,
                }});
                if (isFocused) {{
                    focusedOverlay = overlay;
                }}

                var distanceLabel = point.distance_m >= 1000
                    ? (point.distance_m / 1000).toFixed(1) + 'km'
                    : point.distance_m + 'm';
                var labelContent = '<div style="padding:2px 6px;font-size:11px;background:#fff;' +
                    'border:1px solid ' + color + ';border-radius:4px;white-space:nowrap;' +
                    (isFocused ? 'font-weight:bold;' : '') + '">' +
                    point.name + ' · ' + distanceLabel + '</div>';
                new kakao.maps.CustomOverlay({{
                    position: pos,
                    content: labelContent,
                    yAnchor: 2.4,
                    map: map,
                    zIndex: isFocused ? 100 : 1,
                }});

                new kakao.maps.Polyline({{
                    path: [centerPos, pos],
                    strokeWeight: isFocused ? 3 : 2,
                    strokeColor: color,
                    strokeOpacity: isFocused ? 0.9 : 0.6,
                    strokeStyle: 'shortdash',
                    map: map,
                }});
            }});
        }});

        if (focusedPoint) {{
            map.setCenter(new kakao.maps.LatLng(focusedPoint.lat, focusedPoint.lon));
            map.setLevel(3);
        }} else {{
            map.setBounds(bounds);
        }}

        var legend = document.createElement('div');
        legend.style.position = 'absolute';
        legend.style.top = '10px';
        legend.style.left = '10px';
        legend.style.background = 'rgba(255,255,255,0.9)';
        legend.style.border = '1px solid #ccc';
        legend.style.borderRadius = '6px';
        legend.style.padding = '8px 10px';
        legend.style.fontSize = '12px';
        legend.style.zIndex = '10';
        legend.innerHTML = Object.keys(categories).map(function (key) {{
            var meta = categories[key].meta;
            return '<div style="display:flex;align-items:center;gap:6px;margin:2px 0;">' +
                '<span style="width:10px;height:10px;border-radius:50%;background:' + meta.color + ';display:inline-block;"></span>' +
                '<span>' + meta.icon + ' ' + meta.label + '</span></div>';
        }}).join('');
        container.style.position = 'relative';
        container.appendChild(legend);
    }});
    </script>
    """
    st.components.v1.html(html, height=620)
