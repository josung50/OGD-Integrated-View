from collections.abc import Callable
from typing import Any

import streamlit as st

from ogd_integrated_view.dashboard.kakao_map import render_kakao_map

_RESULT_META = {"label": "결과", "icon": "📍", "color": "#4285F4"}


def _as_categories(map_data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """chat 흐름의 단일 지점 목록({"center", "points"})을 지도 렌더러의 카테고리 형식으로 감싼다."""
    return {"result": {"meta": _RESULT_META, "points": map_data.get("points") or []}}


def render_chat_tab(
    session_key: str,
    description: str,
    placeholder: str,
    examples: list[str],
    query_fn: Callable[[str], dict[str, Any]],
    example_overrides: dict[str, Callable[[str], dict[str, Any]]] | None = None,
) -> None:
    st.caption(description)

    history: list[dict[str, Any]] = st.session_state.setdefault(session_key, [])
    st.caption(f"🔧 진단: 저장된 대화 {len(history)}건")

    asked = False
    if not history:
        st.write("이렇게 물어보세요:")
        for col, example in zip(st.columns(len(examples)), examples):
            if col.button(example, key=f"{session_key}_example_{example}"):
                handler = (example_overrides or {}).get(example, query_fn)
                _ask(history, handler, example)
                asked = True

    user_input = st.chat_input(placeholder, key=f"{session_key}_input")
    if user_input:
        _ask(history, query_fn, user_input)
        asked = True

    # 새로 물어본 직후에는 화면을 한 번 더 그려서, 방금 추가된 메시지가 아래 목록에
    # 바로 반영되도록 한다 (렌더링을 아래 for 루프 한 곳으로만 모아서 중복 표시도 막는다).
    if asked:
        st.rerun()

    for message in history:
        with st.chat_message(message["role"]):
            st.write(message["content"])
            if message.get("map"):
                render_kakao_map(message["map"]["center"], _as_categories(message["map"]))


def _ask(
    history: list[dict[str, Any]],
    query_fn: Callable[[str], dict[str, Any]],
    question: str,
) -> None:
    history.append({"role": "user", "content": question, "map": None})
    with st.spinner("조회 중..."):
        result = query_fn(question)
    answer = result.get("answer", "") if isinstance(result, dict) else result
    map_data = result.get("map") if isinstance(result, dict) else None
    history.append({"role": "assistant", "content": answer, "map": map_data})
