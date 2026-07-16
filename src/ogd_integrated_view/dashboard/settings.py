import shlex
from pathlib import Path

import streamlit as st

from ogd_integrated_view.mcp.config_store import (
    load_app_settings,
    load_servers,
    save_app_settings,
    save_servers,
)

ROLE_LABELS = {
    "real_estate": "🏠 부동산정보확인",
    "law": "⚖️ 법령 및 판례",
    "real_estate_2": "🏠 부동산정보확인 2",
    "location_analysis": "📍 부동산 입지분석",
}
ROLES_WITHOUT_TOOL_NAME = {"real_estate", "real_estate_2", "location_analysis"}

REAL_ESTATE_VENDOR_PATH = Path("vendor/real-estate-mcp").resolve()
REAL_ESTATE_PRESET = {
    "name": "real-estate",
    "role": "real_estate",
    "command": "uv",
    "args": [
        "run",
        "--directory",
        str(REAL_ESTATE_VENDOR_PATH),
        "python",
        "src/real_estate/mcp_server/server.py",
    ],
    "tool_name": "",
    "query_param": "",
    "extra_arguments": {},
}

REAL_ESTATE_2_VENDOR_PATH = Path("vendor/realestate-mcp").resolve()
REAL_ESTATE_2_PRESET = {
    "name": "realestate-mcp",
    "role": "real_estate_2",
    "command": "node",
    "args": [str(REAL_ESTATE_2_VENDOR_PATH / "server.js")],
    "tool_name": "",
    "query_param": "",
    "extra_arguments": {},
}

LOCATION_ANALYSIS_VENDOR_PATH = Path("vendor/A2A-MCP-RealEstate").resolve()
LOCATION_ANALYSIS_PRESET = {
    "name": "A2A-MCP-RealEstate",
    "role": "location_analysis",
    "command": str(LOCATION_ANALYSIS_VENDOR_PATH / ".venv" / "Scripts" / "python.exe"),
    "args": ["app/mcp/real_estate_recommendation_mcp.py"],
    "cwd": str(LOCATION_ANALYSIS_VENDOR_PATH),
    "tool_name": "",
    "query_param": "",
    "extra_arguments": {},
}


def render_settings_tab() -> None:
    st.caption(
        "각 탭에서 사용할 MCP 서버 접속 정보를 등록하세요. "
        "등록하면 해당 탭이 목업 응답 대신 실제 MCP 서버를 호출합니다. "
        "API 키 등 민감정보가 그대로 저장되니(data/mcp_servers.json, git에는 포함되지 않음) 개인 환경에서만 사용하세요."
    )

    servers = load_servers()

    st.subheader("AI 기반 응답 (선택)")
    st.caption(
        "정해진 질문 패턴이 아니라 자유로운 자연어 질문에 대해 LLM이 MCP tool을 알아서 호출해 "
        "답변하도록 할 수 있습니다 (두 탭 모두 적용). 아무 것도 등록하지 않으면 지금처럼 규칙 기반으로 동작합니다."
    )
    app_settings = load_app_settings()

    st.markdown("**로컬 LLM (Ollama, 무료)**")
    st.caption(
        "Ollama가 로컬에서 실행 중이어야 합니다 (`ollama serve`). "
        "tool calling을 지원하는 모델만 사용 가능합니다 (예: qwen3:1.7b — 테스트 완료, gemma3는 미지원)."
    )
    local_model = st.text_input(
        "로컬 모델명",
        value=app_settings.get("local_model", ""),
        placeholder="예: qwen3:1.7b",
        key="local_model_input",
    )
    if st.button("로컬 LLM 설정 저장", key="save_local_model"):
        app_settings["local_model"] = local_model
        save_app_settings(app_settings)
        st.success("저장되었습니다." if local_model else "로컬 LLM이 비활성화되었습니다 (모델명이 비어있습니다).")
        st.rerun()

    st.markdown("**클라우드 LLM (Anthropic, 유료)**")
    st.caption("로컬 모델명이 등록되어 있으면 클라우드보다 로컬이 우선 사용됩니다.")
    anthropic_key = st.text_input(
        "ANTHROPIC_API_KEY",
        type="password",
        value=app_settings.get("anthropic_api_key", ""),
        key="anthropic_api_key_input",
    )
    if st.button("클라우드 LLM 설정 저장", key="save_anthropic_key"):
        app_settings["anthropic_api_key"] = anthropic_key
        save_app_settings(app_settings)
        st.success("저장되었습니다." if anthropic_key else "클라우드 응답이 비활성화되었습니다 (키가 비어있습니다).")
        st.rerun()

    st.divider()

    st.subheader("카카오맵 표시 (선택)")
    st.caption(
        "'부동산 입지분석' 탭에서 분석 결과를 텍스트뿐 아니라 지도로도 보여줍니다. "
        "[카카오 디벨로퍼스](https://developers.kakao.com/)에서 앱을 만든 뒤 "
        "'JavaScript' 키를 발급받아 입력하세요 (위에서 쓰는 REST API 키와는 다른 키입니다). "
        "발급 후 앱 설정 > 플랫폼에 사용 중인 도메인(예: http://localhost:8501)을 등록해야 지도가 로드됩니다."
    )
    kakao_js_key = st.text_input(
        "KAKAO_JS_KEY (JavaScript 키)",
        type="password",
        value=app_settings.get("kakao_js_key", ""),
        key="kakao_js_key_input",
    )
    if st.button("카카오맵 설정 저장", key="save_kakao_js_key"):
        app_settings["kakao_js_key"] = kakao_js_key
        save_app_settings(app_settings)
        st.success("저장되었습니다." if kakao_js_key else "카카오맵 표시가 비활성화되었습니다 (키가 비어있습니다).")
        st.rerun()

    st.divider()

    st.subheader("빠른 설정 — 부동산 실거래가 (real-estate-mcp)")
    st.caption("공공데이터포털에서 발급받은 API 키만 입력하면 나머지 접속 정보는 자동으로 채워집니다.")
    api_key = st.text_input(
        "DATA_GO_KR_API_KEY", type="password", key="quick_real_estate_api_key"
    )
    if st.button("부동산 MCP 저장", key="quick_real_estate_save"):
        if not api_key:
            st.error("API 키를 입력하세요.")
        else:
            servers = [s for s in servers if s.get("role") != "real_estate"]
            servers.append({**REAL_ESTATE_PRESET, "env": {"DATA_GO_KR_API_KEY": api_key}})
            save_servers(servers)
            st.success("부동산 MCP 서버가 저장되었습니다.")
            st.rerun()

    st.divider()

    st.subheader("빠른 설정 — 부동산 실거래가 2 (realestate-mcp)")
    st.caption(
        "지역명·아파트명·읍면동 필터를 tool이 직접 지원하는 서버입니다. "
        "공공데이터포털 인증키는 동일 계정이면 위 서버와 같은 키를 그대로 써도 됩니다."
    )
    existing_key = next(
        (s.get("env", {}).get("DATA_GO_KR_API_KEY", "") for s in servers if s.get("role") == "real_estate"),
        "",
    )
    api_key_2 = st.text_input(
        "REALESTATE_API_KEY", type="password", value=existing_key, key="quick_real_estate_2_api_key"
    )
    if st.button("부동산 MCP 2 저장", key="quick_real_estate_2_save"):
        if not api_key_2:
            st.error("API 키를 입력하세요.")
        else:
            servers = [s for s in servers if s.get("role") != "real_estate_2"]
            servers.append({**REAL_ESTATE_2_PRESET, "env": {"REALESTATE_API_KEY": api_key_2}})
            save_servers(servers)
            st.success("부동산 MCP 2 서버가 저장되었습니다.")
            st.rerun()

    st.divider()

    st.subheader("빠른 설정 — 부동산 입지분석 (A2A-MCP-RealEstate)")
    st.caption(
        "지하철역/편의시설 거리 기반 입지 분석, 투자가치·삶의질 평가, 도로명 주소 검색을 지원합니다. "
        "공공데이터포털 인증키(MOLIT)는 위와 동일 계정 키를 재사용할 수 있고, "
        "네이버 지도 키는 [네이버클라우드플랫폼](https://www.ncloud.com/), "
        "카카오 키는 [카카오 디벨로퍼스](https://developers.kakao.com/)에서 별도 발급해야 합니다."
    )
    existing_location_env = next(
        (s.get("env", {}) for s in servers if s.get("role") == "location_analysis"), {}
    )
    existing_molit_key = existing_location_env.get("MOLIT_API_KEY") or next(
        (s.get("env", {}).get("DATA_GO_KR_API_KEY", "") for s in servers if s.get("role") == "real_estate"),
        "",
    )
    molit_key = st.text_input(
        "MOLIT_API_KEY", type="password", value=existing_molit_key, key="quick_location_molit_key"
    )
    naver_client_id = st.text_input(
        "NAVER_CLIENT_ID", value=existing_location_env.get("NAVER_CLIENT_ID", ""), key="quick_location_naver_id"
    )
    naver_client_secret = st.text_input(
        "NAVER_CLIENT_SECRET",
        type="password",
        value=existing_location_env.get("NAVER_CLIENT_SECRET", ""),
        key="quick_location_naver_secret",
    )
    kakao_api_key = st.text_input(
        "KAKAO_API_KEY (REST API 키)",
        type="password",
        value=existing_location_env.get("KAKAO_API_KEY", ""),
        key="quick_location_kakao_key",
    )
    st.caption(
        "네이버/카카오 키가 없으면 각각 위치 분석, 주변 시설 검색 기능이 동작하지 않습니다 "
        "(MOLIT 키만으로도 등록은 가능합니다)."
    )
    if st.button("부동산 입지분석 MCP 저장", key="quick_location_save"):
        if not molit_key:
            st.error("MOLIT_API_KEY는 필수입니다.")
        else:
            servers = [s for s in servers if s.get("role") != "location_analysis"]
            servers.append(
                {
                    **LOCATION_ANALYSIS_PRESET,
                    "env": {
                        "MOLIT_API_KEY": molit_key,
                        "NAVER_CLIENT_ID": naver_client_id,
                        "NAVER_CLIENT_SECRET": naver_client_secret,
                        "KAKAO_API_KEY": kakao_api_key,
                    },
                }
            )
            save_servers(servers)
            st.success("부동산 입지분석 MCP 서버가 저장되었습니다.")
            st.rerun()

    st.divider()

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
        name = st.text_input("이름", placeholder="예: real-estate")
        role = st.selectbox(
            "연결할 탭", options=list(ROLE_LABELS.keys()), format_func=lambda r: ROLE_LABELS[r]
        )
        command = st.text_input("실행 명령어", placeholder="예: uv")
        args_text = st.text_input(
            "인자 (공백으로 구분, 경로에 공백이 있으면 큰따옴표로 감싸기)",
            placeholder='run --directory "C:/path/to/server" python src/server.py',
        )
        env_text = st.text_area(
            "환경변수 / API 키 (한 줄에 하나씩, KEY=VALUE 형식)", placeholder="DATA_GO_KR_API_KEY=발급받은키"
        )

        tool_name = ""
        query_param = ""
        if role in ROLES_WITHOUT_TOOL_NAME:
            st.caption(
                f"'{ROLE_LABELS[role]}' 탭은 내부적으로 필요한 tool을 자동으로 순서대로 호출하므로 "
                "tool 이름을 따로 입력하지 않아도 됩니다."
            )
        else:
            tool_name = st.text_input("호출할 tool 이름", placeholder="예: search_law")
            query_param = st.text_input("질문을 전달할 tool 파라미터 이름", value="query")

        submitted = st.form_submit_button("저장")
        if submitted:
            if not name or not command:
                st.error("이름, 실행 명령어는 필수입니다.")
            elif role not in ROLES_WITHOUT_TOOL_NAME and not tool_name:
                st.error("tool 이름은 필수입니다.")
            else:
                env = {}
                for line in env_text.splitlines():
                    if "=" in line:
                        key, _, value = line.partition("=")
                        env[key.strip()] = value.strip()
                try:
                    args = shlex.split(args_text)
                except ValueError as exc:
                    st.error(f"인자를 해석할 수 없습니다 (따옴표를 확인하세요): {exc}")
                else:
                    servers.append(
                        {
                            "name": name,
                            "role": role,
                            "command": command,
                            "args": args,
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
