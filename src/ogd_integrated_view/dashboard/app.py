import sys

import streamlit as st

from ogd_integrated_view.dashboard.backend import (
    query_law,
    query_location_analysis,
    query_real_estate,
    query_real_estate_2,
)
from ogd_integrated_view.dashboard.chat import render_chat_tab
from ogd_integrated_view.dashboard.settings import render_settings_tab

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def main() -> None:
    st.set_page_config(page_title="OGD Integrated View", page_icon="🗂️", layout="wide")
    st.title("OGD Integrated View")
    st.write("궁금한 내용을 편하게 질문해보세요. 각 탭은 해당 공공데이터에만 답합니다.")

    tab_real_estate, tab_law, tab_real_estate_2, tab_location_analysis, tab_settings = st.tabs(
        ["🏠 부동산정보확인", "⚖️ 법령 및 판례", "🏠 부동산정보확인 2", "📍 부동산 입지분석", "⚙️ 설정"]
    )

    with tab_real_estate:
        render_chat_tab(
            session_key="real_estate_chat",
            description="국토교통부 부동산 실거래가 정보를 확인할 수 있습니다.",
            placeholder="예: 서울 강남구 아파트 최근 실거래가 알려줘",
            examples=["서울 강남구 아파트 실거래가", "부산 해운대구 아파트 시세"],
            query_fn=query_real_estate,
        )

    with tab_real_estate_2:
        render_chat_tab(
            session_key="real_estate_2_chat",
            description="국토교통부 부동산 실거래가 정보를 확인할 수 있습니다 (realestate-mcp — 아파트명/읍면동 필터 지원).",
            placeholder="예: 성남시 분당구 래미안 아파트 매매 내역 알려줘",
            examples=["강남구 대치동 아파트 실거래가", "래미안 아파트 매매 내역만 필터링해줘"],
            query_fn=query_real_estate_2,
        )

    with tab_location_analysis:
        render_chat_tab(
            session_key="location_analysis_chat",
            description="지하철역/편의시설 거리 기반 입지 분석, 투자가치·삶의질 평가를 확인할 수 있습니다.",
            placeholder="예: 서울 강남구 대치동 은마아파트 입지 분석해줘",
            examples=["서울 강남구 대치동 은마아파트 입지 분석", "판교역 근처 아파트 삶의질 평가"],
            query_fn=query_location_analysis,
        )

    with tab_law:
        render_chat_tab(
            session_key="law_chat",
            description="법제처 법령 및 판례 정보를 확인할 수 있습니다.",
            placeholder="예: 주택임대차보호법 최신 개정 내용 알려줘",
            examples=["주택임대차보호법 조항", "임대차 관련 판례"],
            query_fn=query_law,
        )

    with tab_settings:
        render_settings_tab()


if __name__ == "__main__":
    main()
