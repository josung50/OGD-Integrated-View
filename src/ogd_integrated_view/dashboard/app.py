import streamlit as st

from ogd_integrated_view.dashboard.backend import query_law, query_real_estate
from ogd_integrated_view.dashboard.chat import render_chat_tab
from ogd_integrated_view.dashboard.settings import render_settings_tab


def main() -> None:
    st.set_page_config(page_title="OGD Integrated View", page_icon="🗂️", layout="wide")
    st.title("OGD Integrated View")
    st.write("궁금한 내용을 편하게 질문해보세요. 각 탭은 해당 공공데이터에만 답합니다.")

    tab_real_estate, tab_law, tab_settings = st.tabs(
        ["🏠 부동산정보확인", "⚖️ 법령 및 판례", "⚙️ 설정"]
    )

    with tab_real_estate:
        render_chat_tab(
            session_key="real_estate_chat",
            description="국토교통부 부동산 실거래가 정보를 확인할 수 있습니다.",
            placeholder="예: 서울 강남구 아파트 최근 실거래가 알려줘",
            examples=["서울 강남구 아파트 실거래가", "부산 해운대구 아파트 시세"],
            query_fn=query_real_estate,
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
