import asyncio
import traceback
from typing import Any

from ogd_integrated_view.mcp.agent import ask as ask_cloud_agent
from ogd_integrated_view.mcp.client import call_tool
from ogd_integrated_view.mcp.config_store import load_app_settings
from ogd_integrated_view.mcp.local_agent import ask as ask_local_agent
from ogd_integrated_view.mcp.registry import find_server_by_role


def query_location_analysis(question: str) -> dict[str, Any]:
    return _query("location_analysis", question)


def _query(role: str, question: str) -> dict[str, Any]:
    server = find_server_by_role(role)
    if server is None:
        return {"answer": _mock(question), "map": None}

    settings = load_app_settings()
    local_model = settings.get("local_model")
    api_key = settings.get("anthropic_api_key")

    try:
        if local_model:
            return asyncio.run(ask_local_agent(server, question, local_model))
        if api_key:
            return asyncio.run(ask_cloud_agent(server, question, api_key))
        result = asyncio.run(call_tool(server, question))
        return {"answer": _format_result(result), "map": None}
    except Exception as exc:
        print(f"[backend] {role} query failed:\n{traceback.format_exc()}", flush=True)
        return {"answer": f"MCP 서버 호출 중 오류가 발생했습니다: {exc}", "map": None}


def _mock(question: str) -> str:
    return (
        f"'{question}'에 대한 응답입니다. (목업 응답)\n\n"
        "설정 탭에서 MCP 서버를 등록하면 실제 결과로 대체됩니다."
    )


def _format_result(result: object) -> str:
    content = getattr(result, "content", None)
    if not content:
        return str(result)
    parts = [getattr(item, "text", None) or str(item) for item in content]
    return "\n\n".join(parts)
