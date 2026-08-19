"""BOB SSAFY(Streamlit 앱) — 코너 사진 폴백. 브라우저로 렌더된 img 태그를 읽습니다."""

from __future__ import annotations

import os

from lunchbot.welplan import COURSE_STATIONS

# playwright는 브라우저를 띄울 때만 필요해서 함수 안에서 import 합니다.

IFRAME = 'iframe[title="streamlitApp"]'
APP_READY = "text=BOB SSAFY"
MENU_READY = "text=메인 메뉴"
MENU_MARKERS = ("메인 메뉴", "오늘의 메뉴")
LOGIN_ERROR = "Not logged in"
WELMENU_HOST = "img-welmenu.welstory.com"

# BOB SSAFY 페이지의 사진 DOM 순서 (메인 4코너 → 추가배식대 → 마이보글)
STATION_ORDER = tuple(COURSE_STATIONS[code] for code in ("A1", "AA", "BB", "CC", "HH", "DD"))

CI = bool(os.getenv("CI"))
# CI 러너는 느려서 무한정 기다리는 대신 빨리 포기하고 다른 사진 소스로 넘어갑니다.
DEFAULT_TIMEOUT_MS = 45_000 if CI else 90_000
ATTEMPT_TIMEOUT_MS = 25_000 if CI else DEFAULT_TIMEOUT_MS
POLL_ATTEMPTS = 2 if CI else 4
SETTLE_MS = 1_500 if CI else 2_500
RETRY_MS = 2_000 if CI else 4_000
RENDER_MS = 1_000 if CI else 2_000


class BobssafyError(RuntimeError):
    pass


def default_timeout_ms() -> int:
    raw = os.getenv("BOBSSAFY_TIMEOUT_MS", "").strip()
    return int(raw) if raw else DEFAULT_TIMEOUT_MS


def is_welmenu_image_url(url: str) -> bool:
    return bool(url) and url.startswith("http") and WELMENU_HOST in url


def map_welmenu_images(urls: list[str]) -> dict[str, str]:
    """welmenu 이미지 URL 목록을 DOM 순서대로 코너명에 짝지웁니다."""
    menu_urls = [url for url in urls if is_welmenu_image_url(url)]
    return dict(zip(STATION_ORDER, menu_urls))


def _wait_for_menu(app, page, timeout_ms: int) -> None:
    """Streamlit이 메뉴 본문을 그릴 때까지 폴링합니다."""
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

    attempt_timeout = min(timeout_ms, ATTEMPT_TIMEOUT_MS)
    for attempt in range(POLL_ATTEMPTS):
        page.wait_for_timeout(SETTLE_MS)
        text = app.locator("body").inner_text(timeout=attempt_timeout)
        if LOGIN_ERROR in text:
            raise BobssafyError(
                "BOB SSAFY가 메뉴 원본에 로그인하지 못한 상태입니다. "
                "사이트에서 메뉴가 보이는지 확인한 뒤 다시 실행해 주세요."
            )
        if any(marker in text for marker in MENU_MARKERS):
            try:
                app.locator(MENU_READY).first.wait_for(timeout=10_000)
            except PlaywrightTimeoutError:
                pass
            return
        if attempt < POLL_ATTEMPTS - 1:
            page.wait_for_timeout(RETRY_MS)
    raise BobssafyError("BOB SSAFY 페이지에서 메뉴 본문을 찾지 못했습니다.")


def fetch_photos(url: str, timeout_ms: int | None = None) -> dict[str, str]:
    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise BobssafyError(
            "playwright가 없습니다. pip install -r requirements.txt 후 "
            "python -m playwright install chromium 을 실행해 주세요."
        ) from exc

    limit = timeout_ms if timeout_ms is not None else default_timeout_ms()
    with sync_playwright() as playwright:
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
        page = context.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=limit)
            app = page.frame_locator(IFRAME)
            app.locator(APP_READY).first.wait_for(timeout=limit)
            _wait_for_menu(app, page, limit)
            page.wait_for_timeout(RENDER_MS)

            urls = [(img.get_attribute("src") or "").strip() for img in app.locator("img").all()]
            photos = map_welmenu_images(urls)
            if not photos:
                raise BobssafyError("BOB SSAFY 페이지에서 welmenu 사진 URL을 찾지 못했습니다.")
            return photos
        except PlaywrightTimeoutError as exc:
            raise BobssafyError(f"BOB SSAFY 페이지 로딩이 시간 초과되었습니다: {url}") from exc
        finally:
            context.close()
            browser.close()
