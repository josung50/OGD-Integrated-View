# 아키텍처 설계안

## 1. 전체 흐름

```
[API 정의(config)]  ─┐
                      ├→ [수집기 Collector] → [통합 저장소 Storage] → [Streamlit 대시보드]
[MCP 서버 정의(config)]─┘
```

1. `apis/`, `mcp/` 아래에 각각 소스(REST API / MCP 서버)의 정의(엔드포인트 또는 서버 실행정보, 인증키, 호출할 tool 등)를 등록
2. `collectors/`가 두 종류의 정의를 모두 읽어 실제로 호출하고, 원시 응답을 저장 (1차 단계는 가공 없이 그대로 저장)
3. `storage/`가 데이터를 통합 데이터셋(엑셀)에 저장
4. `dashboard/`가 저장된 데이터를 읽어 Streamlit으로 시각화 (1차는 가공 없이 결과값 그대로 표시)

## 2. 폴더 구조

```
src/ogd_integrated_view/
├── apis/                    # API 정의 (수백 개까지 확장 고려)
│   ├── __init__.py
│   ├── base.py              # 공통 API 클라이언트 베이스 클래스
│   ├── registry.py          # 등록된 API 정의를 모아서 로딩
│   └── definitions/         # API 1개당 파일 1개 (설정 + 응답 매핑)
│       ├── __init__.py
│       └── example_api.py
├── mcp/                      # MCP 서버 정의 (API와 병렬 구조)
│   ├── __init__.py
│   ├── base.py               # 공통 McpServerDefinition 베이스 클래스
│   ├── client.py              # MCP 서버 연결/도구(tool) 호출 공통 로직
│   ├── registry.py            # 등록된 MCP 서버 정의를 모아서 로딩
│   └── definitions/           # MCP 서버 1개당 파일 1개
│       ├── __init__.py
│       ├── moleg.py           # 예: 법제처 MCP 서버
│       └── real_estate.py     # 예: 부동산 실거래가 MCP 서버
├── collectors/
│   ├── __init__.py
│   └── collector.py         # apis/mcp definitions를 모두 순회하며 데이터 수집 실행
├── storage/
│   ├── __init__.py
│   ├── db.py                 # SQLite 연결/스키마 관리
│   └── repository.py         # 저장/조회 인터페이스 (추후 DB 교체 대비)
├── dashboard/
│   ├── __init__.py
│   └── app.py                 # Streamlit 진입점
└── main.py                    # CLI 진입점 (수집 실행 트리거)
```

## 3. API 정의 방식 (수백 개 확장 고려)

API가 수백 개로 늘어난다는 요구사항을 고려해, `definitions/` 아래 **API 1개당 파일 1개**로 관리합니다.
각 정의는 공통 베이스 클래스를 상속해 아래 정보만 채우면 되도록 설계합니다.

```python
# apis/definitions/example_api.py
from ogd_integrated_view.apis.base import ApiDefinition

class ExampleApi(ApiDefinition):
    name = "example_api"
    base_url = "https://api.example.go.kr/v1/resource"
    auth_type = "api_key"          # none / api_key / oauth 등
    params = {"perPage": 100}

    def normalize(self, raw_response: dict) -> list[dict]:
        """API 응답을 통합 스키마의 레코드 리스트로 변환"""
        ...
```

`registry.py`가 `definitions/` 폴더를 스캔해 자동으로 모든 API를 인식하므로,
새 API를 추가할 때는 파일 하나만 만들면 됩니다 (등록 코드를 따로 수정할 필요 없음).

## 3-1. MCP 서버 정의 방식

법제처, 부동산 실거래가처럼 **MCP 서버를 통해 데이터를 가져오는 소스**를 API와 동일한 패턴으로 관리합니다.
`definitions/` 아래 **서버 1개당 파일 1개**로, 접속 정보(커맨드/URL), 인증키(환경변수 참조), 호출할 tool과 인자를 정의합니다.

```python
# mcp/definitions/moleg.py  (법제처 MCP 서버 예시)
from ogd_integrated_view.mcp.base import McpServerDefinition

class MolegApi(McpServerDefinition):
    name = "moleg"
    command = "npx"                       # stdio 방식 실행 커맨드 (또는 url= 로 http/sse 방식)
    args = ["-y", "moleg-mcp-server"]
    env = {"MOLEG_API_KEY": "${MOLEG_API_KEY}"}   # .env에서 값을 채워넣음
    tool_name = "search_law"
    tool_arguments = {"query": "..."}
```

- API 키 등 민감정보는 코드에 직접 쓰지 않고 프로젝트 루트의 `.env` 파일에서 로드 (`python-dotenv`)
- `registry.py`가 `definitions/` 폴더를 자동 스캔하는 것은 `apis/`와 동일한 패턴
- **1차 목표는 가공 없이 결과값 그대로 보여주는 것**이므로, `normalize()`는 당장 스키마 매핑을 하지 않고
  MCP tool 호출 결과를 최대한 그대로(raw JSON을 컬럼 하나에 담는 방식 등) 저장

## 4. 저장소 (Storage)

- **최종 저장 형태: 엑셀(.xlsx) 파일** (SQLite 아님, 확정)
- 저장 위치: `data/ogd_integrated.xlsx`
- 구조(가안 — 미확인 상태, 추후 조정 가능):
  - 통합 파일 1개, 소스(API)별 시트 + `통합` 시트로 전체를 모아보는 구조
  - 갱신 방식: 추가/병합(Append+Upsert) — 재수집 시 key 기준으로 기존 행 갱신, 신규 행 추가
- `repository.py`에 저장/조회 인터페이스를 두어, pandas의 `read_excel`/`ExcelWriter`를 감싸는 형태로 구현
  (대시보드와 수집기는 저장 형식이 바뀌어도 인터페이스만 보고 동작)
- 의존성 추가 필요: `openpyxl` (pandas의 xlsx 읽기/쓰기 엔진)

## 5. 대시보드

- **Streamlit** 사용, `storage/repository.py`를 통해 데이터 조회
- 1차 화면 구성(제안):
  - API 소스별 데이터 현황(수집 건수, 최근 수집 시각)
  - 통합 데이터 테이블/필터
  - 소스별 트렌드 차트

## 6. 미정 사항 (확인 필요)

- [x] ~~DB를 SQLite로 확정할지~~ → 엑셀(.xlsx) 파일로 확정
- [x] ~~API 인증정보 관리 방식~~ → `.env` + `python-dotenv`로 확정 (MCP 서버 인증키도 동일하게 관리)
- [ ] 엑셀 파일 구조: 통합 파일 1개(시트 여러 개) / 소스별 파일+통합 파일 / 단일 통합 시트만 — **임시로 "통합 파일 1개 + 소스별 시트" 가정**
- [ ] 재수집 시 갱신 방식: 덮어쓰기 / 추가·병합 — **임시로 "추가·병합" 가정**
- [ ] 수집 실행 주기 (수동 실행 / 스케줄러(cron 등) 필요 여부)
- [ ] 대시보드 배포 방식 (로컬 실행만 할지, 서버에 올릴지)
- [ ] 연동할 MCP 서버 목록 확정 (법제처, 부동산 실거래가 외 추가 예정 있는지)
- [ ] 각 MCP 서버의 실행 방식 확인 (stdio 커맨드 / http·sse URL) 및 필요한 API 키 목록
