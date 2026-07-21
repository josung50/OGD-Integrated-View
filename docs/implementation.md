# 구현 현황 (Implementation Reference)

`architecture.md`/`requirements.md`는 초기 설계안이고, 이 문서는 **실제로 구현되어 동작 중인 내용**을
유지보수 관점에서 정리한 것입니다. 코드가 바뀌면 이 문서도 함께 업데이트하세요.

## 1. 한눈에 보기

```
Streamlit 대시보드 (dashboard/app.py)
├── 📍 부동산 입지분석 탭 (location_dashboard.py)
│   ├── 주소 검색 폼 → analyze_all() → A2A-MCP-RealEstate MCP 서버 → 카카오맵 표시
│   └── 자유 질의 챗 (chat.py)
│       ├── "실거주자 의견종합" → 호갱노노 스크래핑 (hogangnono_scraper.py)
│       └── 그 외 질문 → LLM 에이전트(로컬 Ollama or 클라우드 Claude) + MCP tool 자동 호출
└── ⚙️ 설정 탭 (settings.py)
    ├── MCP 서버 등록/삭제 (data/mcp_servers.json)
    ├── LLM 설정 (로컬 모델명 / Anthropic API 키) (data/app_settings.json)
    ├── 카카오맵 JS 키
    └── 공공데이터(횡단보도) 최신화 버튼

CLI 배치 수집 (main.py)
└── collect_all() — apis/definitions + mcp 서버들을 순회하며 data/ogd_integrated.xlsx에 저장
```

핵심 설계 원칙: **API/MCP 정의는 파일 1개당 1개, `registry.py`가 폴더를 스캔해 자동 등록**한다.
새 공공데이터 API를 추가할 때 등록 코드를 따로 고칠 필요가 없다.

## 2. 폴더별 역할

| 경로 | 역할 |
|---|---|
| `apis/base.py`, `apis/registry.py` | REST API 정의 베이스 클래스 + `apis/definitions/*.py` 자동 스캔 |
| `apis/definitions/crosswalk.py` | 유일하게 등록된 REST API 정의 (전국횡단보도표준데이터) |
| `mcp/base.py`, `mcp/registry.py` | MCP 서버 정의 베이스 클래스 + `mcp/definitions/*.py` 자동 스캔 + `data/mcp_servers.json`(설정 탭에서 등록한 서버) 병합 |
| `mcp/definitions/` | 코드로 하드코딩된 MCP 서버 정의 (현재 비어 있음 — 실제로는 설정 탭에서 등록한 A2A-MCP-RealEstate 하나만 사용 중) |
| `mcp/client.py` | MCP stdio 클라이언트 공통 로직 (`call_tool`), `months_ago()` 유틸 |
| `mcp/agent.py` | 클라우드(Claude) 기반 tool-use 에이전트 — MCP tool 목록을 Claude에게 주고 자동 호출 |
| `mcp/local_agent.py` | 로컬(Ollama) 기반 tool-use 에이전트 — 위와 동일한 역할을 로컬 모델로 수행 |
| `mcp/region_lookup.py` | 텍스트에서 시/군/구 이름 → 법정동코드(LAWD_CD) 매핑 (`mcp/data/lawd_codes.json`) |
| `mcp/building_lookup.py` | 카카오 로컬 API로 도로명주소 ↔ 건물명 변환 |
| `mcp/location_pipeline.py` | `analyze_all()` — 입지분석 탭의 "주소 검색" 폼이 쓰는 고정 파이프라인 (LLM에게 맡기지 않고 4가지 조회를 순서대로 실행) |
| `mcp/hogangnono_scraper.py` | 호갱노노 로그인/검색/AI요약 Playwright 스크래퍼 (MCP 서버 아님, 순수 파이썬 모듈) |
| `mcp/crosswalk_check.py` | 횡단보도 데이터 로드 + 두 지점 사이 횡단보도 유무 판정 |
| `mcp/config_store.py` | `data/mcp_servers.json`, `data/app_settings.json` 읽기/쓰기 |
| `collectors/collector.py` | API/MCP 정의를 순회해 실제로 호출하고 `Repository`에 저장 (`collect_all`, `refresh_api`) |
| `storage/repository.py` | 통합 저장소 — `data/ogd_integrated.xlsx`의 시트 단위 저장/조회 (pandas + openpyxl) |
| `dashboard/app.py` | Streamlit 진입점, 탭 2개(입지분석/설정) 등록 |
| `dashboard/location_dashboard.py` | 입지분석 탭 UI + 호갱노노 실거주자 의견종합 로직 |
| `dashboard/chat.py` | 재사용 가능한 채팅 UI 컴포넌트 (`render_chat_tab`) |
| `dashboard/kakao_map.py` | 카카오맵 JS SDK를 `st.components.v1.html`로 임베드해 마커/거리선 렌더링 |
| `dashboard/backend.py` | 챗 질문 → LLM 에이전트(로컬/클라우드) 또는 MCP tool 직접 호출로 라우팅 |
| `dashboard/settings.py` | 설정 탭 UI — MCP 서버/LLM/카카오 키/공공데이터 갱신 |

## 3. 기능 상세

### 3-1. 부동산 입지분석 (주소 검색 폼)

- 진입점: `location_dashboard.py:render_location_dashboard`
- 흐름: 주소 + 반경(km) 입력 → `mcp/location_pipeline.py:analyze_all()` 호출
  - `resolve_address()`(카카오 키워드 검색)로 "은마아파트" 같은 단지명을 도로명주소로 정규화
  - `analyze_location` tool 1회 → 좌표 + 가까운 지하철역
  - `find_nearby_facilities` tool을 카테고리별로 반복 호출 → 편의점/카페/은행/약국(`convenience`), 대학병원/대형마트(`infra`), 학교(`schools`)
  - `get_nearby_apartment_transactions` tool 1회 → 반경 내 아파트 실거래(3개월)
  - 각 카테고리 최대 15건으로 트리밍, 거래 항목은 도로명 대신 실제 건물명으로 보강(`find_building_name`)
- 결과는 5개 카테고리(`subway`/`convenience`/`infra`/`schools`/`transactions`)로 나뉘어 팝오버 표 + 카카오맵 마커로 표시
- 표에서 행을 클릭하면 지도가 해당 지점으로 포커스 이동 (`_FOCUS_POINT_KEY`)

### 3-2. 자유 질의 챗 (일반 LLM 경로)

- 진입점: `location_dashboard.py`의 "💬 추가로 질문하기" 익스팬더 → `chat.py:render_chat_tab`
- 기본 핸들러: `_query_with_context()` → `backend.py:query_location_analysis()`
- LLM 우선순위: **로컬 모델명이 설정되어 있으면 로컬(Ollama) 우선, 없으면 클라우드(Claude) 키 사용, 둘 다 없으면 A2A-MCP-RealEstate의 `analyze_location` tool을 단순 호출한 결과를 그대로 보여주는 목업 모드**
- 로컬: `mcp/local_agent.py:ask()` (모델은 tool calling 지원 필요 — 테스트 완료: `qwen3:1.7b`, 미지원: `gemma3`)
- 클라우드: `mcp/agent.py:ask()` (모델: `claude-sonnet-5`, `MAX_TOOL_ROUNDS=6`)
- 두 에이전트 모두 거의 동일한 구조: MCP tool 목록을 LLM에게 주고 최대 6라운드까지 자동 호출 → 최종 텍스트 답변 + 지도 데이터(`_extract_map_data`) 추출
- 작은 모델의 실수를 코드로 방어하는 로직들 (`_sanitize_arguments`):
  - `dong` 파라미터가 실제 동/읍/면/리 이름이 아니면 제거
  - 지역 코드(`sido_cd`/`sgg_cd`/`lawd_cd`)는 질문에서 지역명을 다시 찾아 강제로 덮어씀 (`region_lookup.py`)
  - "2026년 1월부터 6월까지" 같은 기간 표현을 파싱해 `start_year_month`/`end_year_month`에 강제로 채움
  - `months` 값이 상식 범위(1~60)를 벗어나면 삭제
  - 좌표 변환 실패 시 서울시청 기본좌표로 "성공 위장"하는 응답을 감지해 `[경고: ...]` 문구를 앞에 붙임 (`_flag_location_fallback`)

### 3-3. 실거주자 의견종합 (호갱노노)

- 예시 버튼/문구: `RESIDENT_OPINION_EXAMPLE = "실거주자 의견종합"` (`location_dashboard.py:22`)
- **버튼 클릭과 채팅창에 같은 문구를 타이핑하는 것 모두 동일하게** `example_overrides`를 거쳐
  `_fetch_resident_opinions()`로 라우팅됨 (`chat.py`가 버튼 클릭과 타이핑 입력 모두에 `example_overrides` 매핑을 적용)
- 흐름 (`location_dashboard.py:_fetch_resident_opinions`):
  1. 세션에 캐시된 쿠키 없으면 `hogangnono_scraper.py:capture_login_session()` 호출 → **카카오 로그인 창만** 사용자에게 보여줌(홈페이지/모달은 백그라운드에서 헤드리스로 처리)
  2. `find_apartment_url()` — 캐시된 쿠키로 호갱노노 검색창에 아파트명/주소 입력 → 상세페이지 URL
  3. `_fetch_all_category_summaries()` — `AI_SUMMARY_CATEGORIES` 9개 카테고리를 동시(최대 4개 동시)에 조회해 각 카테고리의 AI 요약 문단만 추출해 합침
  4. 실패 시 세 가지로 구분해서 처리 (아래 "알아두어야 할 함정" 참고)

### 3-4. 설정 탭

- MCP 서버 등록/삭제 (`data/mcp_servers.json`, git 미포함)
- LLM 설정: 로컬 모델명 / Anthropic API 키 (`data/app_settings.json`)
- 카카오맵 JS 키 (지도 렌더링용, REST API 키와는 별도)
- "부동산 입지분석 MCP 저장" — MOLIT/네이버/카카오 키를 입력하면 `LOCATION_ANALYSIS_PRESET`으로 A2A-MCP-RealEstate 서버를 자동 등록
- 공공데이터(횡단보도) "최신화" 버튼 — `collectors/collector.py:refresh_api()` 호출, 시트를 통째로 교체(append 아님)

## 4. 사용 중인 외부 API

| API | 용도 | 키 이름 | 호출 위치 |
|---|---|---|---|
| 공공데이터포털 — 전국횡단보도표준데이터 | 도보 경로상 횡단보도 유무 판정용 원본 데이터 | `PUBLIC_DATA_API_KEY` | `apis/definitions/crosswalk.py` |
| 공공데이터포털 — 국토교통부(MOLIT) 실거래가 | 아파트 실거래가 조회 | `MOLIT_API_KEY` (A2A-MCP-RealEstate 서버 env) | vendor MCP 서버 내부 |
| 카카오 로컬 API (주소/키워드 검색) | 건물명 조회, 단지명→도로명주소 정규화, 지역 검색(A2A 서버) | `KAKAO_API_KEY` (REST) | `mcp/building_lookup.py`, A2A 서버 |
| 카카오맵 JavaScript SDK | 대시보드 지도 렌더링 | `KAKAO_JS_KEY` (JS, REST키와 별도) | `dashboard/kakao_map.py` |
| 네이버 지도(Geocoding) | 주소→좌표 변환 (A2A 서버의 1차 지오코더) | `NAVER_CLIENT_ID`/`NAVER_CLIENT_SECRET` | A2A 서버 내부 |
| Anthropic Claude API | 클라우드 LLM 에이전트 (모델: `claude-sonnet-5`) | `anthropic_api_key` (앱 설정) | `mcp/agent.py` |
| Ollama (로컬) | 로컬 LLM 에이전트, tool calling 지원 모델 필요 | 없음 (로컬 서버) | `mcp/local_agent.py` |
| 호갱노노 (hogangnono.com) | 실거주자 리뷰 AI 요약 — 공식 API 아님, Playwright로 화면을 직접 조작하는 스크래핑 | 없음 (카카오 소셜 로그인 세션 쿠키만 사용) | `mcp/hogangnono_scraper.py` |

## 5. MCP 서버 상세 — A2A-MCP-RealEstate

`vendor/A2A-MCP-RealEstate` (별도 리포지토리, FastMCP 기반 stdio 서버).
설정 탭에서 `role: "location_analysis"`로 등록하면 입지분석 탭·자유질의 챗이 이 서버를 사용한다.
실행: `python app/mcp/real_estate_recommendation_mcp.py` (해당 vendor 폴더의 자체 `.venv` 사용).

| Tool | 설명 |
|---|---|
| `analyze_location(address, lat?, lon?)` | 주소→좌표, 가까운 지하철역, 위치 점수(`calculate_location_score`: 교통 40% + 편의성 35% + 환경 25%) |
| `find_nearby_facilities(address, category, radius)` | 카카오 로컬 API 기반 반경 내 시설 검색 |
| `get_nearby_apartment_transactions(address, lawd_cd, region_name, radius_km, months, start_year_month?, end_year_month?, ...)` | 반경 내 아파트 실거래가 + 좌표 (지도 표시용) |
| `search_by_road_address(road_address, date_from?, date_to?, property_type, deal_type)` | 도로명주소로 실거래 직접 조회 |
| `get_real_estate_data_advanced(...)` | MOLIT 원자료를 더 세밀한 조건으로 조회 |
| `get_regional_price_statistics(lawd_cd?, region?, property_type, months)` | 지역 평당가 통계 |
| `compare_similar_properties(...)` | 유사 매물 비교 |
| `evaluate_investment_value(address, price, area, floor, total_floor, building_year, property_type, deal_type)` | 투자가치 점수 — 가격 25% + 면적 20% + 층수 15% + 교통 25% + 미래발전가능성(건축연한·역세권) 15% |
| `evaluate_life_quality(같은 파라미터)` | 삶의질 점수 — 환경 25% + 편의성 25% + 안전 20% + 교육 15% + 문화 15% |
| `recommend_property(..., user_preference)` | 위 점수들을 종합한 매물 추천 |
| `get_region_codes()` | 법정동코드 조회 |
| `get_usage_guide()` | 서버 자체 사용 가이드 텍스트 |

> ⚠️ 이 스코어링 함수들은 **고정된 규칙 기반**(하드코딩된 임계값·가중치)이며 실시간 시세 예측 모델이 아니다.
> 실제 매물의 가격·면적·층수·건축연도 등 어떤 값을 이 함수에 넣을지는 LLM 에이전트가 대화 맥락과 다른 tool 결과를 보고 채운다.
> 상세 로직은 `vendor/A2A-MCP-RealEstate/app/mcp/real_estate_recommendation_mcp.py`, `app/mcp/location_service.py` 참고.

## 6. 호갱노노 스크래퍼 — 알아두어야 할 함정

MCP 서버가 아니라 Playwright로 실제 브라우저를 조작하는 방식이라, 유지보수 시 아래 사항을 꼭 알아야 함.

- **로그인은 절대 자격증명을 다루지 않는다** — 사용자가 실제 카카오 로그인 창에서 직접 로그인하고,
  완료 시점의 세션 쿠키(`connect.sid`/`client.cid`/`bat`)만 캡처해 메모리(`st.session_state`)에만 보관한다 (디스크 저장 안 함).
- **로그인 흐름 최적화** (`capture_login_session`, `_get_fresh_kakao_login_url`):
  - 홈페이지 진입 → 모달 닫기 → 게스트 로그인 클릭 → 카카오 로그인 버튼 클릭까지는 **헤드리스**로 처리해
    "카카오 로그인 창"만 사용자 눈앞에 뜨게 한다.
  - "카카오 계정으로 로그인"은 같은 페이지 이동이 아니라 **새 팝업**을 연다 — `context.expect_page()`로 감지해야 함.
  - Playwright 드라이버 프로세스는 헤드리스/헤드풀 브라우저가 하나를 공유하도록 재사용(약 1.5초 절약),
    헤드풀 브라우저 launch는 헤드리스 URL 확보와 **동시에** 시작한다.
  - 랜덤하게 뜨는 홍보/설치유도 모달이 로그인 모달과 같은 슬롯을 써서 밀어내는 경우가 있어,
    카카오 로그인 버튼이 보일 때까지 (모달 닫기 → 재클릭)을 최대 4회 재시도한다.
- **헤드리스 봇 감지** — `fetch_ai_summary`(AI 요약 조회)는 세션 쿠키가 완전히 유효해도 **헤드리스로 열면
  호갱노노가 감지해서 `/auth`로 튕겨보낸다.** 원인은 User-Agent에 남는 `HeadlessChrome`/전체 빌드번호,
  `window.chrome` 부재, `navigator.plugins` 빈 배열 등 — `_stealth_user_agent()` + `_STEALTH_INIT_SCRIPT`로
  헤드풀과 동일하게 위장해서 우회 중이다. **호갱노노가 감지 방식을 바꾸면 이 우회도 다시 깨질 수 있다.**
- **AI 요약 페이지는 category 파라미터가 필수** — `?category=` 없이 접근하면 404. 실제 사이트 탭에서 확인한
  유효값은 `AI_SUMMARY_CATEGORIES` 9개뿐 (`주변 자연환경/교통/생활 인프라/소음/주변 개발 호재/커뮤니티 시설/학군/주차/구조 및 조망`).
  이 목록이 사이트에서 바뀌면 하드코딩된 리스트도 같이 갱신해야 한다.
- **9개 카테고리 병렬 조회의 실패 처리** — 동시 실행을 4개로 제한(`_MAX_CONCURRENT_SUMMARY_FETCHES`)해도
  리소스 경합으로 개별 카테고리가 타임아웃날 수 있다. 세 가지 결과를 구분해서 처리한다:
  1. `HogangnonoSessionExpired` (실제 `/auth` 리다이렉트) → 캐시된 쿠키를 지우고 재로그인 요구
  2. `HogangnonoNoReviewData` ("페이지가 존재하지 않습니다" 안내 페이지 — 소규모 단지처럼 리뷰 자체가 없는 경우) → 오류가 아니라 "리뷰 데이터가 없습니다"로 안내, 쿠키는 유지
  3. 그 외 개별 타임아웃/오류 → 그 카테고리만 건너뛰고 나머지는 정상 반환, 쿠키는 유지
- **쿠키 도메인은 반드시 `.hogangnono.com`(점 포함)** — 실제 브라우저가 쓰는 형식과 다르면
  재구성한 쿠키가 새 브라우저 인스턴스에서 인증으로 안 잡힐 수 있다.
- 디버그 실패 시 `data/sources/_debug_ai_summary.png` 스크린샷이 남는다 (`.gitignore`의 `data/sources/`로 git 추적 제외).

## 7. 데이터 저장

- `data/ogd_integrated.xlsx` — CLI 배치 수집(`main.py` → `collect_all`) 결과. 소스(API/MCP 이름)별 시트로 저장, 기본은 append, `refresh_api()`는 시트 전체 교체.
- `data/mcp_servers.json` — 설정 탭에서 등록한 MCP 서버 목록 (API 키 평문 포함, git 미포함)
- `data/app_settings.json` — 로컬 모델명 / Anthropic 키 / 카카오 JS 키 (git 미포함)
- `data/sources/` — 스크래핑 실패 시 디버그 스크린샷 (git 미포함)
- 호갱노노 세션 쿠키는 **디스크에 저장하지 않고** `st.session_state`(브라우저 세션 메모리)에만 유지

## 8. 실행 방법

```bash
# 대시보드
uv run streamlit run src/ogd_integrated_view/dashboard/app.py

# CLI 배치 수집 (data/ogd_integrated.xlsx 갱신)
uv run python -m ogd_integrated_view.main
```

설정 탭에서 최소 A2A-MCP-RealEstate(MOLIT 키 필수, 네이버/카카오 키는 선택이지만 없으면 관련 기능 비활성)를
등록해야 입지분석 탭이 목업 응답이 아닌 실제 데이터를 보여준다.
