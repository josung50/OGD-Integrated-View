# OGD Integrated View

여러 공공데이터(Open Government Data) API 및 MCP 서버에서 데이터를 수집해 하나의 통합 데이터셋(엑셀 파일)으로
저장하고, 이를 기반으로 Streamlit 대시보드를 제공하는 프로젝트입니다.

## 배경

- 연동할 공공데이터 API가 수백 개까지 늘어날 수 있어, API 정의를 체계적으로 관리할 구조가 필요합니다.
- 법제처, 부동산 실거래가처럼 **MCP 서버를 통해 가져오는 데이터**도 있어, API와 동일한 방식으로 관리할 구조가 필요합니다.
- 수집한 데이터는 하나로 통합해서 보관하고, 통합된 데이터를 대시보드로 확인할 수 있어야 합니다.
- 1차 목표는 별도 가공 없이 수집한 결과값을 그대로 보여주는 것입니다.

## 핵심 목표

1. 수백 개 규모로 늘어날 수 있는 API를 별도 폴더/구조로 관리 (API 1개당 파일 1개, 자동 등록)
2. 법제처·부동산 실거래가 등 MCP 서버 기반 데이터 소스도 API와 동일한 패턴으로 관리
3. 각 소스(API/MCP)에서 데이터를 수집해 통합 데이터셋으로 저장
4. 저장된 데이터를 가공 없이 대시보드로 그대로 제공 (1차 목표)

## 전체 흐름

```
[API 정의(config)]  ─┐
                      ├→ [수집기 Collector] → [통합 저장소 Storage] → [Streamlit 대시보드]
[MCP 서버 정의(config)]─┘
```

## 폴더 구조 (설계안)

```
src/ogd_integrated_view/
├── apis/                    # API 정의 (수백 개까지 확장 고려)
│   ├── base.py              # 공통 API 클라이언트 베이스 클래스
│   ├── registry.py          # definitions/ 를 스캔해 자동 등록
│   └── definitions/         # API 1개당 파일 1개
├── mcp/                      # MCP 서버 정의 (API와 병렬 구조)
│   ├── base.py               # 공통 McpServerDefinition 베이스 클래스
│   ├── client.py              # MCP 서버 연결/도구(tool) 호출 공통 로직
│   ├── registry.py            # definitions/ 를 스캔해 자동 등록
│   └── definitions/           # MCP 서버 1개당 파일 1개 (예: 법제처, 부동산 실거래가)
├── collectors/                 # apis/mcp definitions를 모두 순회하며 데이터 수집 실행
├── storage/                     # 엑셀 저장/조회 (repository.py가 인터페이스 역할)
├── dashboard/                    # Streamlit 진입점 (app.py)
└── main.py                       # CLI 진입점 (수집 실행 트리거)
```

## 기술 스택

| 항목 | 내용 |
|------|------|
| 언어/런타임 | Python 3.14 (uv로 관리) |
| 의존성 | requests, pandas, openpyxl, streamlit, mcp(예정), python-dotenv(예정) |
| 데이터 저장 | 엑셀(.xlsx) — `data/ogd_integrated.xlsx` (DB 사용 안 함) |
| 대시보드 | Streamlit |
| 인증정보 관리 | `.env` + python-dotenv (API 키, MCP 서버 인증키 등) |

## 데이터 저장 방식

- 최종 저장 형태는 **엑셀(.xlsx) 파일**로 확정 (SQLite 등 DB 사용하지 않음)
- 구조(가안, 확인 필요): 통합 파일 1개 + 소스(API)별 시트 + 전체를 모아보는 `통합` 시트
- 재수집 시 갱신 방식(가안, 확인 필요): 덮어쓰기가 아닌 추가/병합(Upsert)

## 진행 상태 / 미정 사항

- [x] 대시보드 프레임워크 → Streamlit 확정
- [x] 저장 형식 → 엑셀(.xlsx) 확정
- [x] 인증정보 관리 방식 → `.env` + python-dotenv 확정
- [ ] 엑셀 파일 구조 (통합 파일 1개 vs 소스별 파일 분리) — 임시로 "통합 파일 1개 + 소스별 시트"로 가정
- [ ] 재수집 시 갱신 방식 (덮어쓰기 vs 추가·병합) — 임시로 "추가·병합"으로 가정
- [ ] 수집 실행 주기 (수동 실행 / 스케줄러 필요 여부)
- [ ] 대시보드 배포 방식 (로컬 전용 / 서버)
- [ ] 연동할 MCP 서버 목록 및 각 서버의 실행 방식(stdio/http) 확정 (법제처, 부동산 실거래가 외 추가 예정 확인)

## 문서

- [요구사항 정의서](docs/requirements.md)
- [아키텍처 설계안](docs/architecture.md)

## 개발 환경 설정

```bash
uv sync
uv run python --version   # 3.14.x 확인
```
