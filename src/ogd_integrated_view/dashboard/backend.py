import asyncio

from ogd_integrated_view.mcp.client import call_tool
from ogd_integrated_view.mcp.registry import find_server_by_role


def query_real_estate(question: str) -> str:
    return _query("real_estate", question)


def query_law(question: str) -> str:
    return _query("law", question)


def _query(role: str, question: str) -> str:
    server = find_server_by_role(role)
    if server is None:
        return (
            f"'{question}'에 대한 응답입니다. (목업 응답)\n\n"
            "설정 탭에서 MCP 서버를 등록하면 실제 결과로 대체됩니다."
        )
    try:
        result = asyncio.run(call_tool(server, question))
    except Exception as exc:
        return f"MCP 서버 호출 중 오류가 발생했습니다: {exc}"
    return _format_result(result)


def _format_result(result: object) -> str:
    content = getattr(result, "content", None)
    if not content:
        return str(result)
    parts = [getattr(item, "text", None) or str(item) for item in content]
    return "\n\n".join(parts)
