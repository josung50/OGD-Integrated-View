def query_real_estate(question: str) -> str:
    return (
        f"'{question}'에 대한 부동산 실거래가 조회 결과입니다. (목업 응답)\n\n"
        "실제 MCP 서버 연결 전이라 예시 데이터입니다."
    )


def query_law(question: str) -> str:
    return (
        f"'{question}'에 대한 법령 및 판례 검색 결과입니다. (목업 응답)\n\n"
        "실제 MCP 서버 연결 전이라 예시 데이터입니다."
    )
