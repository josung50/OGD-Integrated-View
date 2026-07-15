from collections.abc import Callable

import streamlit as st


def render_chat_tab(
    session_key: str,
    description: str,
    placeholder: str,
    examples: list[str],
    query_fn: Callable[[str], str],
) -> None:
    st.caption(description)

    history: list[dict[str, str]] = st.session_state.setdefault(session_key, [])

    if not history:
        st.write("이렇게 물어보세요:")
        for col, example in zip(st.columns(len(examples)), examples):
            if col.button(example, key=f"{session_key}_example_{example}"):
                _ask(session_key, history, query_fn, example)

    for message in history:
        with st.chat_message(message["role"]):
            st.write(message["content"])

    user_input = st.chat_input(placeholder, key=f"{session_key}_input")
    if user_input:
        _ask(session_key, history, query_fn, user_input)


def _ask(
    session_key: str,
    history: list[dict[str, str]],
    query_fn: Callable[[str], str],
    question: str,
) -> None:
    history.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.write(question)
    with st.chat_message("assistant"):
        with st.spinner("조회 중..."):
            answer = query_fn(question)
        st.write(answer)
    history.append({"role": "assistant", "content": answer})
