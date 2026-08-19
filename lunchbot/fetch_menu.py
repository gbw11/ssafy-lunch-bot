from __future__ import annotations

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from lunchbot.parse_menu import DayMenu, parse_menu_text
from lunchbot.timeutil import now_in

IFRAME = 'iframe[title="streamlitApp"]'
APP_READY = "text=BOB SSAFY"
MENU_READY = "text=메인 메뉴"
LOGIN_ERROR = "Not logged in"


def _browser_context(playwright):
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context(
        locale="ko-KR",
        timezone_id="Asia/Seoul",
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        viewport={"width": 1280, "height": 2400},
    )
    return browser, context


def fetch_menu_page_text(url: str, timeout_ms: int = 90_000) -> str:
    last_text = ""
    with sync_playwright() as playwright:
        browser, context = _browser_context(playwright)
        page = context.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            app = page.frame_locator(IFRAME)
            app.locator(APP_READY).first.wait_for(timeout=timeout_ms)

            for attempt in range(4):
                page.wait_for_timeout(2500)
                last_text = app.locator("body").inner_text(timeout=timeout_ms)
                if LOGIN_ERROR in last_text:
                    page.reload(wait_until="domcontentloaded")
                    app.locator(APP_READY).first.wait_for(timeout=timeout_ms)
                    continue
                if "메인 메뉴" in last_text or "오늘의 메뉴" in last_text:
                    try:
                        app.locator(MENU_READY).first.wait_for(timeout=15_000)
                    except PlaywrightTimeoutError:
                        pass
                    return app.locator("body").inner_text(timeout=timeout_ms)
                if attempt < 3:
                    page.wait_for_timeout(4000)

            if LOGIN_ERROR in last_text:
                raise RuntimeError(
                    "BOB SSAFY가 메뉴 원본에 로그인하지 못한 상태입니다. "
                    "사이트에서 메뉴가 보이는지 확인한 뒤 다시 실행해 주세요."
                )
            raise RuntimeError("BOB SSAFY 페이지에서 메뉴 본문을 찾지 못했습니다.")
        except PlaywrightTimeoutError as exc:
            raise RuntimeError(f"BOB SSAFY 페이지 로딩이 시간 초과되었습니다: {url}") from exc
        finally:
            context.close()
            browser.close()


def fetch_today_menu(url: str, timezone: str = "Asia/Seoul") -> DayMenu:
    today = now_in(timezone).strftime("%Y-%m-%d")
    text = fetch_menu_page_text(url)
    return parse_menu_text(text, date_label=today)
