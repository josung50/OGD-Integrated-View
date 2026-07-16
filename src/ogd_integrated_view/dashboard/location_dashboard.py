import asyncio

import pandas as pd
import streamlit as st

from ogd_integrated_view.dashboard.chat import render_chat_tab
from ogd_integrated_view.dashboard.kakao_map import CATEGORY_META, render_kakao_map
from ogd_integrated_view.dashboard.backend import query_location_analysis
from ogd_integrated_view.mcp.location_pipeline import analyze_all
from ogd_integrated_view.mcp.registry import find_server_by_role

_RESULT_KEY = "location_dashboard_result"
_FOCUS_POINT_KEY = "location_dashboard_focus_point"
_PREV_SELECTION_KEY = "location_dashboard_prev_selection"


def render_location_dashboard() -> None:
    st.caption(
        "주소를 입력하고 분석하면 반경 내 지하철역·편의시설·주요 인프라(대학병원/대형마트)·"
        "아파트 실거래를 지도에 표시합니다."
    )

    with st.form("location_dashboard_form"):
        col_addr, col_radius, col_btn = st.columns([4, 1, 1])
        col_addr.caption("주소")
        col_radius.caption("반경(km)")
        col_btn.caption("​")
        address = col_addr.text_input(
            "주소",
            placeholder="예: 서울 강남구 대치동 은마아파트",
            key="location_dashboard_address",
            label_visibility="collapsed",
        )
        radius_km = col_radius.number_input(
            "반경(km)",
            min_value=0.5,
            max_value=5.0,
            value=1.0,
            step=0.5,
            key="location_dashboard_radius",
            label_visibility="collapsed",
        )
        analyze_clicked = col_btn.form_submit_button("분석", use_container_width=True)

    if analyze_clicked:
        if not address:
            st.error("주소를 입력하세요.")
        else:
            server = find_server_by_role("location_analysis")
            if server is None:
                st.error("설정 탭에서 '부동산 입지분석' MCP 서버를 먼저 등록하세요.")
            else:
                with st.spinner("반경 내 지하철역·편의시설·인프라·실거래를 조회하는 중..."):
                    st.session_state[_RESULT_KEY] = asyncio.run(analyze_all(server, address, radius_km))
                # 새로 분석한 주소로 대화 맥락이 바뀌었으니, 이전 주소를 기준으로 오가던
                # 채팅 기록·지도 포커스는 비워서 이전 주소와 섞이지 않게 한다.
                st.session_state["location_analysis_chat"] = []
                st.session_state[_FOCUS_POINT_KEY] = None
                st.session_state[_PREV_SELECTION_KEY] = {}

    result = st.session_state.get(_RESULT_KEY)
    if not result:
        return
    if not result.get("center"):
        st.warning("주소를 좌표로 변환하지 못했습니다. 더 구체적인 주소를 입력해보세요.")
        return

    categories = {
        key: {"meta": CATEGORY_META[key], "points": points} for key, points in result["categories"].items()
    }

    # 여러 팝오버의 표에 각각 선택 상태가 남아있을 수 있어서, 이전 실행과 비교해
    # "방금 새로 클릭된" 표만 지도 포커스를 바꾸도록 한다 (아니면 다른 탭에 남아있던
    # 예전 선택 때문에 방금 누른 항목이 무시될 수 있다).
    prev_selection: dict[str, tuple[int, ...]] = st.session_state.setdefault(_PREV_SELECTION_KEY, {})
    current_selection: dict[str, tuple[int, ...]] = {}
    new_focus_point = None

    col_map, col_tabs = st.columns([3, 1])
    with col_tabs:
        for key, meta in CATEGORY_META.items():
            points = result["categories"].get(key, [])
            error = result.get("errors", {}).get(key)
            with st.popover(f"{meta['icon']} {meta['label']} ({len(points)})", use_container_width=True):
                if error and not points:
                    st.caption(error)
                elif not points:
                    st.caption("반경 내 정보를 찾지 못했습니다.")
                else:
                    df = pd.DataFrame(
                        [
                            {
                                "이름": p["name"],
                                "거리": f"{p['distance_m']}m" if p["distance_m"] < 1000 else f"{p['distance_m'] / 1000:.1f}km",
                                "정보": p.get("detail", ""),
                                **({"거래일": p.get("date", "")} if key == "transactions" else {}),
                            }
                            for p in points
                        ]
                    )
                    st.caption("행을 클릭하면 지도가 그 위치로 이동합니다.")
                    event = st.dataframe(
                        df,
                        hide_index=True,
                        use_container_width=True,
                        on_select="rerun",
                        selection_mode="single-row",
                        key=f"location_dashboard_table_{key}",
                    )
                    selected_rows = tuple(event.selection.rows) if event and event.selection else ()
                    current_selection[key] = selected_rows
                    if selected_rows and selected_rows != prev_selection.get(key):
                        selected = points[selected_rows[0]]
                        new_focus_point = {
                            "lat": selected["lat"],
                            "lon": selected["lon"],
                            "label": selected["name"],
                        }

    st.session_state[_PREV_SELECTION_KEY] = current_selection
    if new_focus_point:
        st.session_state[_FOCUS_POINT_KEY] = new_focus_point

    focused_point = st.session_state.get(_FOCUS_POINT_KEY)
    with col_map:
        if focused_point:
            if st.button("↩️ 전체 보기로 돌아가기"):
                st.session_state[_FOCUS_POINT_KEY] = None
                focused_point = None
        render_kakao_map(result["center"], categories, focused_point=focused_point)

    address_context = result["center"]["label"]

    def _query_with_context(question: str):
        return query_location_analysis(f"[분석 대상 주소: {address_context}] {question}")

    st.divider()
    with st.expander("💬 추가로 질문하기 (AI에게 자유롭게 물어보기)"):
        st.caption(f"현재 '{address_context}' 기준으로 질문에 답합니다.")
        render_chat_tab(
            session_key="location_analysis_chat",
            description="위 분석과 별개로, 자유로운 질문을 던지면 AI가 필요한 조회를 알아서 수행합니다.",
            placeholder="예: 이 아파트 투자가치 평가해줘",
            examples=["이 위치 투자가치 평가해줘", "주변 학원 알려줘"],
            query_fn=_query_with_context,
        )
