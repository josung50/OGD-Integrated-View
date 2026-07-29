import asyncio

import streamlit as st

from ogd_integrated_view.mcp.gemini_scraper import ask_gemini, ensure_browser_open

_ANSWER_KEY = "gemini_test_answer"


def render_gemini_test_tab() -> None:
    st.caption(
        "Gemini(gemini.google.com)는 자기 사이트를 iframe에 넣는 것을 막아둬서 화면을 그대로 "
        "보여줄 수는 없습니다. 대신 실제 크롬 창을 하나 띄워 거기서 직접 로그인하면, 그 창에 "
        "자동으로 질문을 보내고 답변만 가져옵니다 (로그인은 한 번만 하면 계속 유지됩니다)."
    )

    if st.button("Gemini 브라우저 열기", key="gemini_open_browser"):
        try:
            ensure_browser_open()
            st.success("브라우저를 열었습니다 (이미 열려있었다면 그대로 사용). 처음이라면 뜬 창에서 로그인해주세요.")
        except Exception as exc:
            st.error(f"브라우저를 여는 중 오류가 발생했습니다: {exc}")

    with st.form("gemini_test_form"):
        question = st.text_area("질문", placeholder="예: 한국의 수도는 어디야?")
        submitted = st.form_submit_button("Gemini에게 물어보기")

    if submitted:
        if not question.strip():
            st.error("질문을 입력하세요.")
        else:
            with st.spinner("Gemini에게 물어보는 중..."):
                try:
                    st.session_state[_ANSWER_KEY] = asyncio.run(ask_gemini(question))
                except Exception as exc:
                    st.session_state[_ANSWER_KEY] = f"오류가 발생했습니다: {exc}"

    answer = st.session_state.get(_ANSWER_KEY)
    if answer:
        st.markdown(f"**답변**\n\n{answer}")
