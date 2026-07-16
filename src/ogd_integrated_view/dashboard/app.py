import sys

import streamlit as st

from ogd_integrated_view.dashboard.location_dashboard import render_location_dashboard
from ogd_integrated_view.dashboard.settings import render_settings_tab

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def main() -> None:
    st.set_page_config(page_title="OGD Integrated View", page_icon="🗂️", layout="wide")
    st.title("OGD Integrated View")
    st.write("주소를 입력해 주변 입지 정보를 지도로 확인해보세요.")

    tab_location_analysis, tab_settings = st.tabs(["📍 부동산 입지분석", "⚙️ 설정"])

    with tab_location_analysis:
        render_location_dashboard()

    with tab_settings:
        render_settings_tab()


if __name__ == "__main__":
    main()
