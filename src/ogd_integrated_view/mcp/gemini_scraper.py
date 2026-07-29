import time
import urllib.error
import urllib.request
from pathlib import Path

from playwright.async_api import async_playwright

GEMINI_URL = "https://gemini.google.com/app"
DEBUG_PORT = 9333
# 실제 구글 로그인 세션이 담기는 곳이라 프로젝트 폴더(git 저장소) 밖, 사용자 홈 디렉터리에 둔다.
PROFILE_DIR = Path.home() / ".ogd_integrated_view" / "gemini_chrome_profile"
PAGE_LOAD_TIMEOUT_MS = 30_000
RESPONSE_TIMEOUT_MS = 60_000
_RESPONSE_SELECTOR = ".model-response-text"

_CHROME_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]


def _find_chrome_exe() -> str:
    for path in _CHROME_CANDIDATES:
        if Path(path).exists():
            return path
    raise RuntimeError("설치된 크롬(chrome.exe)을 찾지 못했습니다.")


def _is_debug_port_open() -> bool:
    try:
        urllib.request.urlopen(f"http://localhost:{DEBUG_PORT}/json/version", timeout=1)
        return True
    except (urllib.error.URLError, OSError):
        return False


def ensure_browser_open() -> None:
    """실제 크롬을 자동화 플래그 없이(원격 디버깅 포트만 열어서) 띄운다.

    구글은 Playwright/Selenium 등이 새로 띄운(=자동화 플래그가 붙은) 브라우저에서
    로그인을 시도하면 "지원되지 않는 브라우저" 오류로 차단한다. 여기서는 로그인 자체를
    자동화하지 않는다 — 이 창은 평범하게 실행된 크롬일 뿐이고, 로그인은 사용자가 직접
    한다. 이후 ask_gemini()가 CDP로 이 창에 "연결"만 해서 입력/출력만 자동화하므로
    로그인 시점에는 자동화 흔적이 전혀 없다.

    프로필을 영구 디렉터리(PROFILE_DIR)에 저장해두므로, 한 번 로그인해두면 창을
    새로 열어도 로그인 상태가 유지된다. 이미 떠 있으면 아무 것도 하지 않는다.
    """
    if _is_debug_port_open():
        return
    import subprocess

    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    subprocess.Popen(
        [
            _find_chrome_exe(),
            f"--remote-debugging-port={DEBUG_PORT}",
            f"--user-data-dir={PROFILE_DIR}",
            GEMINI_URL,
        ],
        creationflags=subprocess.DETACHED_PROCESS,
    )


async def ask_gemini(question: str) -> str:
    """ensure_browser_open()으로 띄워둔(그리고 사용자가 직접 로그인해둔) 크롬 창에
    CDP로 연결해 질문을 입력하고 답변 텍스트를 받아온다.

    같은 창/탭을 계속 재사용하므로 대화가 이어진다 — 매번 새 대화를 시작하지 않는다.
    """
    if not _is_debug_port_open():
        raise RuntimeError("Gemini 브라우저가 열려있지 않습니다. 먼저 브라우저를 열어주세요.")

    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(f"http://localhost:{DEBUG_PORT}")
        try:
            context = browser.contexts[0]
            page = next((pg for pg in context.pages if "gemini.google.com" in pg.url), None)
            if page is None:
                page = await context.new_page()
                await page.goto(GEMINI_URL, timeout=PAGE_LOAD_TIMEOUT_MS, wait_until="domcontentloaded")

            responses = page.locator(_RESPONSE_SELECTOR)
            previous_count = await responses.count()

            input_box = page.locator('div[contenteditable="true"]').first
            await input_box.wait_for(state="visible", timeout=PAGE_LOAD_TIMEOUT_MS)
            await input_box.click()
            # 위치분석 데이터를 컨텍스트로 붙이면 질문이 1000자를 훌쩍 넘길 수 있는데,
            # type()은 한 글자씩 키 이벤트를 보내 길면 30초 기본 타임아웃을 넘기고,
            # 입력창에 절반만 쳐진 채로 남는다. fill()은 한 번에 값을 넣어 즉시 끝난다.
            await input_box.fill(question)
            await page.keyboard.press("Enter")

            # 새 응답 말풍선이 실제로 추가될 때까지 먼저 기다린다 (그래야 직전 질문의
            # 답변을 "새 답변"으로 잘못 집어오지 않는다).
            deadline = time.monotonic() + 10
            while await responses.count() <= previous_count and time.monotonic() < deadline:
                await page.wait_for_timeout(300)

            response = responses.last
            await response.wait_for(state="visible", timeout=RESPONSE_TIMEOUT_MS)

            # 텍스트가 잠깐 안 바뀐다고 "다 끝났다"고 보면, 스트리밍 도중의 짧은 끊김을
            # 완료로 오판해 긴 답변이 중간에 잘릴 수 있다. Gemini는 답변을 생성하는 동안
            # 전송 버튼이 "중지(Stop)" 버튼으로 바뀌었다가 끝나면 사라지므로, 이 버튼이
            # 없어질 때까지 기다리는 게 훨씬 확실한 완료 신호다.
            await page.wait_for_timeout(500)  # 버튼이 "중지"로 바뀔 시간을 잠깐 준다
            stop_button = page.locator('button[aria-label*="중지"], button[aria-label*="Stop"]')
            deadline = time.monotonic() + RESPONSE_TIMEOUT_MS / 1000
            while await stop_button.count() > 0 and time.monotonic() < deadline:
                await page.wait_for_timeout(500)

            text = (await response.inner_text()).strip()
            return text or "(응답 없음)"
        finally:
            # CDP 연결만 끊는다 - connect_over_cdp로 붙은 것이라 close()해도 실제
            # 크롬 창은 계속 열려있다 (다음 호출에서 다시 연결해 재사용한다).
            await browser.close()
