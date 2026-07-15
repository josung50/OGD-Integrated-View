import streamlit as st

from ogd_integrated_view.mcp.config_store import load_servers, save_servers

ROLE_LABELS = {"real_estate": "🏠 부동산정보확인", "law": "⚖️ 법령 및 판례"}


def render_settings_tab() -> None:
    st.caption(
        "각 탭에서 사용할 MCP 서버 접속 정보를 등록하세요. "
        "등록하면 해당 탭이 목업 응답 대신 실제 MCP 서버를 호출합니다. "
        "API 키 등 민감정보가 그대로 저장되니(data/mcp_servers.json, git에는 포함되지 않음) 개인 환경에서만 사용하세요."
    )

    servers = load_servers()

    st.subheader("등록된 MCP 서버")
    if not servers:
        st.info("아직 등록된 MCP 서버가 없습니다. 아래에서 추가해보세요.")
    for i, server in enumerate(servers):
        label = ROLE_LABELS.get(server.get("role"), server.get("role") or "역할 미지정")
        with st.expander(f"{label} — {server.get('name')}"):
            st.json(_masked(server))
            if st.button("삭제", key=f"delete_mcp_server_{i}"):
                servers.pop(i)
                save_servers(servers)
                st.rerun()

    st.subheader("새 MCP 서버 추가")
    with st.form("add_mcp_server", clear_on_submit=True):
        name = st.text_input("이름", placeholder="예: moleg")
        role = st.selectbox(
            "연결할 탭", options=list(ROLE_LABELS.keys()), format_func=lambda r: ROLE_LABELS[r]
        )
        command = st.text_input("실행 명령어", placeholder="예: npx")
        args_text = st.text_input("인자 (공백으로 구분)", placeholder="예: -y moleg-mcp-server")
        env_text = st.text_area(
            "환경변수 / API 키 (한 줄에 하나씩, KEY=VALUE 형식)", placeholder="MOLEG_API_KEY=발급받은키"
        )
        tool_name = st.text_input("호출할 tool 이름", placeholder="예: search_law")
        query_param = st.text_input("질문을 전달할 tool 파라미터 이름", value="query")

        submitted = st.form_submit_button("저장")
        if submitted:
            if not name or not command or not tool_name:
                st.error("이름, 실행 명령어, tool 이름은 필수입니다.")
            else:
                env = {}
                for line in env_text.splitlines():
                    if "=" in line:
                        key, _, value = line.partition("=")
                        env[key.strip()] = value.strip()
                servers.append(
                    {
                        "name": name,
                        "role": role,
                        "command": command,
                        "args": args_text.split(),
                        "env": env,
                        "tool_name": tool_name,
                        "query_param": query_param,
                        "extra_arguments": {},
                    }
                )
                save_servers(servers)
                st.success(f"'{name}' 서버가 저장되었습니다.")
                st.rerun()


def _masked(server: dict) -> dict:
    masked = dict(server)
    masked["env"] = {key: "••••••" for key in server.get("env", {})}
    return masked
