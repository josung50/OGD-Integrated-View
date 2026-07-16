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
) -> None:
    st.caption(description)

    history: list[dict[str, Any]] = st.session_state.setdefault(session_key, [])

    if not history:
        st.write("이렇게 물어보세요:")
        for col, example in zip(st.columns(len(examples)), examples):
            if col.button(example, key=f"{session_key}_example_{example}"):
                _ask(session_key, history, query_fn, example)

    for message in history:
        with st.chat_message(message["role"]):
            st.write(message["content"])
            if message.get("map"):
                render_kakao_map(message["map"]["center"], _as_categories(message["map"]))

    user_input = st.chat_input(placeholder, key=f"{session_key}_input")
    if user_input:
        _ask(session_key, history, query_fn, user_input)


def _ask(
    session_key: str,
    history: list[dict[str, Any]],
    query_fn: Callable[[str], dict[str, Any]],
    question: str,
) -> None:
    history.append({"role": "user", "content": question, "map": None})
    with st.chat_message("user"):
        st.write(question)
    with st.chat_message("assistant"):
        with st.spinner("조회 중..."):
            result = query_fn(question)
        answer = result.get("answer", "") if isinstance(result, dict) else result
        map_data = result.get("map") if isinstance(result, dict) else None
        st.write(answer)
        if map_data:
            render_kakao_map(map_data["center"], _as_categories(map_data))
    history.append({"role": "assistant", "content": answer, "map": map_data})
