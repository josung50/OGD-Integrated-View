import asyncio
import re
import time

from playwright.async_api import async_playwright

class HogangnonoSessionExpired(Exception):
    """쿠키가 실제로 무효화되어 /auth로 리다이렉트된 경우에만 발생시킨다.
    (단순 페이지 타임아웃 등 세션과 무관한 실패와 구분하기 위함 — 9개 카테고리를
    병렬로 조회하다 보면 세션은 멀쩡한데 리소스 경합으로 개별 요청이 타임아웃나는
    경우가 있어, 그런 경우까지 세션 만료로 오판해 캐시된 쿠키를 지우면 안 된다.)"""


class HogangnonoNoReviewData(Exception):
    """해당 카테고리에 리뷰가 없어 호갱노노가 "페이지가 존재하지 않습니다" 안내
    페이지로 보낸 경우. 세션 만료나 일시적 오류가 아니라 그냥 데이터가 없는
    것이므로, 사용자에게 다르게(오류가 아니라 데이터 없음으로) 안내해야 한다."""


HOMEPAGE_URL = "https://hogangnono.com/"
AI_SUMMARY_SELECTOR = "#review-ai-summary-page-scroll"
PAGE_LOAD_TIMEOUT_MS = 30_000
LOGIN_TIMEOUT_S = 300

# AI 요약 페이지(review/ai-summary)는 category 쿼리파라미터 없이는 404가 나고,
# 실제 사이트 탭에서 확인한 유효한 카테고리 값은 이 9개뿐이다.
AI_SUMMARY_CATEGORIES = [
    "주변 자연환경",
    "교통",
    "생활 인프라",
    "소음",
    "주변 개발 호재",
    "커뮤니티 시설",
    "학군",
    "주차",
    "구조 및 조망",
]

# 헤드리스 크로미움은 User-Agent에 전체 빌드 버전("Chrome/149.0.7827.55")과
# "HeadlessChrome"이 그대로 남고, window.chrome이 없고, plugins가 비어있는 등
# 전형적인 지문이 남아서 호갱노노가 이를 감지해 로그인 세션이 있어도 AI 요약처럼
# 로그인 필요한 페이지에서 /auth로 튕겨보낸다. 실제 크로미움은 UA 축소 정책으로
# 빌드 번호를 "0.0"으로 뭉갠 UA("Chrome/149.0.0.0")를 쓰므로 이를 그대로 흉내낸다.
def _stealth_user_agent(browser) -> str:
    major_version = browser.version.split(".")[0]
    return (
        f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        f"(KHTML, like Gecko) Chrome/{major_version}.0.0.0 Safari/537.36"
    )


_STEALTH_INIT_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'languages', { get: () => ['ko-KR', 'ko'] });
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
window.chrome = { runtime: {} };
"""


def _parse_cookie_header(cookie_header: str, domain: str) -> list[dict]:
    """브라우저 개발자도구에서 복사한 'Cookie:' 헤더 문자열을
    playwright의 add_cookies()가 받는 형식으로 변환한다."""
    cookies = []
    for pair in cookie_header.split(";"):
        if "=" not in pair:
            continue
        name, _, value = pair.strip().partition("=")
        cookies.append({"name": name, "value": value, "domain": domain, "path": "/"})
    return cookies


def _cookie_header(cookies: list[dict]) -> str:
    return "; ".join(f"{c['name']}={c['value']}" for c in cookies)


async def _close_intro_modal(page) -> None:
    """앱 설치 유도 모달이나 광고 배너가 로드 시 자동으로 뜨는 경우가 있다.
    data-ga-event="intro,closeBtn"는 화면을 실제로 막고 있는 모달과는 무관한
    숨은 요소를 가리킬 때가 있어 클릭이 "성공"해도 진짜 모달은 안 닫힐 수 있다.
    그래서 하나가 성공해도 멈추지 않고 두 선택자를 모두 시도한 뒤, 그래도 오버레이가
    남아있으면 배경(다이얼로그 바깥 영역)을 직접 클릭해 닫는다. count()로 아예
    없는 선택자는 클릭 타임아웃을 기다리지 않고 바로 건너뛴다."""
    for locator in (
        page.locator('button.text-primary-foreground:has-text("닫기")'),
        page.locator('[data-ga-event="intro,closeBtn"]'),
    ):
        if await locator.count() == 0:
            continue
        try:
            await locator.click(timeout=1200)
            await page.wait_for_timeout(200)
        except Exception:
            pass

    overlay = page.locator('[data-testid="dialog-overlay"]')
    if await overlay.count() > 0:
        try:
            await overlay.click(position={"x": 10, "y": 10}, timeout=1200)
        except Exception:
            pass


async def _get_fresh_kakao_login_url(p) -> str:
    """헤드리스 브라우저로 홈페이지에서 로그인 버튼을 눌러, 카카오가 방금 발급한
    유효한 로그인 URL(매번 새로운 auth_tran_id 포함)만 뽑아낸다. 사용자에게는
    호갱노노 홈페이지를 전혀 보여주지 않고, 이 URL로 바로 보이는 창을 띄우기 위함이다.
    playwright 드라이버 프로세스(p)는 호출자가 띄운 걸 그대로 받아써서 매번
    새로 기동하는 ~1.5초를 아낀다."""
    browser = await p.chromium.launch(headless=True)
    try:
        context = await browser.new_context()
        page = await context.new_page()
        # domcontentloaded까지 안 기다리고 응답이 오는 대로 바로 진행한다 (이후
        # 클릭/대기는 전부 자체 타임아웃으로 요소 등장을 기다리므로 안전하다).
        await page.goto(HOMEPAGE_URL, timeout=PAGE_LOAD_TIMEOUT_MS, wait_until="commit")

        await _close_intro_modal(page)

        # 홍보 모달이 로그인 모달과 같은 슬롯을 써서, 게스트 로그인 클릭 직후에
        # 타이머로 늦게 뜨는 홍보 모달이 방금 연 로그인 모달을 밀어내는 경우가 있다.
        # 카카오 로그인 버튼이 나타날 때까지 (닫기 → 재클릭)을 몇 번 재시도한다.
        kakao_login_btn = page.locator('[data-ga-event="auth,loginKakao"]')
        for _ in range(4):
            try:
                # 채팅/광고 위젯 등 작은 고정 UI가 여전히 살짝 겹치는 경우가 있어 강제로 클릭한다.
                # 홍보 모달이 게스트 로그인 버튼 자체를 display:none으로 가려버리는 경우도 있어
                # (force=True로도 못 뚫음) 이 클릭 실패도 재시도 대상에 포함한다.
                await page.get_by_test_id("guest-login-button").click(timeout=10_000, force=True)
                await kakao_login_btn.wait_for(state="visible", timeout=1200)
                break
            except Exception:
                await _close_intro_modal(page)
        else:
            raise RuntimeError("카카오 로그인 버튼을 찾지 못했습니다 (홍보 모달에 계속 가로막힘).")

        # "카카오 계정으로 로그인"은 같은 페이지에서 이동하지 않고 새 팝업 창을 연다.
        async with context.expect_page(timeout=10_000) as popup_info:
            await kakao_login_btn.click(timeout=5000, force=True)
        popup = await popup_info.value
        await popup.wait_for_load_state("domcontentloaded", timeout=PAGE_LOAD_TIMEOUT_MS)
        if "kakao.com" not in popup.url:
            raise RuntimeError("카카오 로그인 URL을 새로 발급받지 못했습니다.")
        return popup.url
    finally:
        await browser.close()


async def capture_login_session(timeout_s: int = LOGIN_TIMEOUT_S) -> str:
    """카카오 로그인 화면만 사용자 눈앞에 띄워 직접 로그인을 하게 한 뒤,
    로그인 완료 시점의 세션 쿠키를 캡처해 'Cookie:' 헤더 문자열로 반환한다.

    자격증명은 전혀 다루지 않는다 — ID/PW 입력은 전부 사용자가 실제 브라우저 창에서
    직접 한다. 홈페이지 진입/모달 닫기/게스트 로그인 클릭까지는 보이지 않는 브라우저로
    미리 처리해 방금 발급된 유효한 카카오 로그인 URL을 얻고, 그 URL로 바로 보이는
    창을 연다 — 사용자에게는 호갱노노 홈페이지 없이 카카오 로그인 화면만 뜬다.

    완료 여부는 카카오 도메인에 일정 시간 이상 머물다가 다시 hogangnono.com으로
    돌아오는지로 판단한다 (최소 체류 시간을 두는 이유: auth_tran_id가 만료된 경우
    로그인 없이 즉시 에러 리다이렉트가 오는데, 이를 정상 로그인 완료로 착각하지
    않기 위해서다).
    """
    async with async_playwright() as p:
        # 사용자에게 보일 브라우저 창의 launch(약 1초)를, 헤드리스로 로그인 URL을
        # 받아오는 동안 미리 동시에 진행해서 체감 대기시간을 줄인다.
        headed_browser_task = asyncio.ensure_future(p.chromium.launch(headless=False))
        try:
            start_url = await _get_fresh_kakao_login_url(p)
        except Exception:
            try:
                await (await headed_browser_task).close()
            except Exception:
                pass
            raise

        browser = await headed_browser_task
        try:
            context = await browser.new_context()
            page = await context.new_page()
            await page.goto(start_url, timeout=PAGE_LOAD_TIMEOUT_MS)

            deadline = time.monotonic() + timeout_s
            kakao_entered_at: float | None = None
            min_kakao_dwell_s = 3.0
            while time.monotonic() < deadline:
                if "kakao.com" in page.url:
                    if kakao_entered_at is None:
                        kakao_entered_at = time.monotonic()
                elif kakao_entered_at is not None and "hogangnono.com" in page.url:
                    if time.monotonic() - kakao_entered_at >= min_kakao_dwell_s:
                        break
                    kakao_entered_at = None  # 너무 빨리 돌아옴 = 에러 리다이렉트로 판단, 다시 대기
                await page.wait_for_timeout(1000)
            else:
                raise TimeoutError("로그인 대기 시간이 초과되었습니다.")

            await page.wait_for_timeout(1500)  # 리다이렉트 직후 쿠키가 막 세팅되는 순간을 피한다
            cookies = await context.cookies(HOMEPAGE_URL)
            return _cookie_header(cookies)
        except Exception as exc:
            if isinstance(exc, TimeoutError):
                raise
            raise RuntimeError(f"로그인 캡처 중 브라우저 창이 예기치 않게 닫혔습니다: {exc}") from exc
        finally:
            await browser.close()


async def find_apartment_url(query: str, cookie_header: str) -> str | None:
    """홈페이지 검색창으로 아파트를 검색해 상세 페이지 URL을 찾는다."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            context = await browser.new_context()
            await context.add_cookies(_parse_cookie_header(cookie_header, ".hogangnono.com"))
            page = await context.new_page()
            await page.goto(HOMEPAGE_URL, timeout=PAGE_LOAD_TIMEOUT_MS)

            search_input = page.get_by_test_id("search-input")
            await search_input.fill(query)
            await search_input.press("Enter")
            await page.wait_for_timeout(2000)

            # 검색 결과 목록에서 이동할 링크를 고른다 (이미 상세로 바로 이동했으면 그대로 둔다).
            # 클릭은 화면 위 모달/오버레이에 가로막히는 경우가 있어, href를 읽어 직접 이동한다.
            # 첫 번째 결과가 항상 정답은 아니다 — 호갱노노 검색이 "문촌마을7단지아파트"를
            # 검색해도 전혀 다른 지역의 "OO7단지"를 1순위로 주고 실제로 찾는 "문촌마을7단지"는
            # 2순위로 내놓는 경우가 있어, 검색어의 핵심 이름이 그대로 들어간 결과를 우선한다.
            if "/apt/" not in page.url:
                query_core = re.sub(r"(아파트|apt)$", "", query.replace(" ", ""), flags=re.IGNORECASE)
                results = page.locator('a[href*="/apt/"]')
                try:
                    count = await results.count()
                except Exception:
                    count = 0
                href = None
                for i in range(count):
                    result_text = (await results.nth(i).inner_text()).replace(" ", "").replace("\n", "")
                    if query_core and query_core in result_text:
                        href = await results.nth(i).get_attribute("href")
                        break
                if href is None:
                    try:
                        href = await results.first.get_attribute("href", timeout=5000)
                    except Exception:
                        return None
                if not href:
                    return None
                await page.goto(HOMEPAGE_URL.rstrip("/") + href, timeout=PAGE_LOAD_TIMEOUT_MS)

            return page.url if "/apt/" in page.url else None
        finally:
            await browser.close()


def _apt_hash(apt_url: str) -> str | None:
    m = re.search(r"/apt/([^/?]+)", apt_url)
    return m.group(1) if m else None


async def fetch_ai_summary(apt_url: str, cookie_header: str, category: str | None = None) -> str | None:
    """AI 요약 페이지를 브라우저로 열어, JS가 채운 뒤의 텍스트를 가져온다.

    로그인 세션(cookie_header)이 있어야 하고, 요약 텍스트는 페이지 로드 후
    클라이언트 쪽에서 비동기로 채워지는 영역이라 단순 HTTP 요청으로는 가져올 수 없다.
    """
    apt_hash = _apt_hash(apt_url)
    if apt_hash is None:
        return None
    url = f"https://hogangnono.com/apt/{apt_hash}/0/0/review/ai-summary"
    if category:
        url += f"?category={category}"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            context = await browser.new_context(user_agent=_stealth_user_agent(browser), locale="ko-KR")
            await context.add_init_script(_STEALTH_INIT_SCRIPT)
            await context.add_cookies(_parse_cookie_header(cookie_header, ".hogangnono.com"))
            page = await context.new_page()
            await page.goto(url, timeout=PAGE_LOAD_TIMEOUT_MS, wait_until="networkidle")

            container = page.locator(AI_SUMMARY_SELECTOR)
            try:
                await container.wait_for(state="visible", timeout=PAGE_LOAD_TIMEOUT_MS)
                await page.wait_for_timeout(2000)  # 스피너가 사라지고 텍스트로 바뀔 시간을 준다
                text = (await container.inner_text()).strip()
                return text or None
            except Exception as exc:
                print(f"[hogangnono_scraper] 요약 텍스트를 못 가져왔습니다: {exc}", flush=True)
                print(f"[hogangnono_scraper] 최종 URL: {page.url}, 제목: {await page.title()}", flush=True)
                if "/auth" in page.url:
                    raise HogangnonoSessionExpired(f"세션이 만료되어 로그인 페이지로 리다이렉트됨: {page.url}") from exc
                if await page.locator("text=페이지가 존재하지 않습니다").count() > 0:
                    raise HogangnonoNoReviewData(f"'{category}' 카테고리에 리뷰 데이터가 없음") from exc
                debug_path = "data/sources/_debug_ai_summary.png"
                await page.screenshot(path=debug_path)
                print(f"[hogangnono_scraper] 스크린샷 저장: {debug_path}", flush=True)
                return None
        finally:
            await browser.close()
