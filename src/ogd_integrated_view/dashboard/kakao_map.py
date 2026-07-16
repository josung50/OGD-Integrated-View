import json
from typing import Any

import streamlit as st

from ogd_integrated_view.mcp.config_store import load_app_settings

_MAP_COUNTER_KEY = "_kakao_map_counter"


def render_kakao_map(map_data: dict[str, Any]) -> None:
    """중심 위치와 주변 지점을 카카오맵에 마커+거리선으로 그린다.

    JS 키가 설정되어 있지 않으면 지도 대신 안내 메시지만 보여준다.
    """
    js_key = load_app_settings().get("kakao_js_key")
    if not js_key:
        st.info(
            "지도를 보려면 설정 탭에서 카카오 JavaScript 키(KAKAO_JS_KEY)를 등록하세요. "
            "(REST API 키와는 별도의 키입니다.)"
        )
        return

    center = map_data.get("center")
    points = map_data.get("points") or []
    if not center:
        return

    st.session_state[_MAP_COUNTER_KEY] = st.session_state.get(_MAP_COUNTER_KEY, 0) + 1
    element_id = f"kakao-map-{st.session_state[_MAP_COUNTER_KEY]}"

    center_json = json.dumps(center, ensure_ascii=False)
    points_json = json.dumps(points, ensure_ascii=False)

    html = f"""
    <div id="{element_id}" style="width:100%;height:480px;border-radius:8px;"></div>
    <script src="https://dapi.kakao.com/v2/maps/sdk.js?appkey={js_key}&autoload=false"></script>
    <script>
    kakao.maps.load(function () {{
        var center = {center_json};
        var points = {points_json};
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

        points.forEach(function (point) {{
            var pos = new kakao.maps.LatLng(point.lat, point.lon);
            bounds.extend(pos);

            new kakao.maps.Marker({{ position: pos, map: map }});

            var distanceLabel = point.distance_m
                ? (point.distance_m >= 1000
                    ? (point.distance_m / 1000).toFixed(1) + 'km'
                    : point.distance_m + 'm')
                : '';
            var overlayContent = '<div style="padding:2px 6px;font-size:12px;background:#fff;' +
                'border:1px solid #999;border-radius:4px;white-space:nowrap;">' +
                point.name + (point.type ? ' (' + point.type + ')' : '') +
                (distanceLabel ? ' · ' + distanceLabel : '') + '</div>';
            new kakao.maps.CustomOverlay({{
                position: pos,
                content: overlayContent,
                yAnchor: 2.2,
                map: map,
            }});

            new kakao.maps.Polyline({{
                path: [centerPos, pos],
                strokeWeight: 2,
                strokeColor: '#EA4335',
                strokeOpacity: 0.8,
                strokeStyle: 'shortdash',
                map: map,
            }});
        }});

        if (points.length > 0) {{
            map.setBounds(bounds);
        }}
    }});
    </script>
    """
    st.components.v1.html(html, height=500)
