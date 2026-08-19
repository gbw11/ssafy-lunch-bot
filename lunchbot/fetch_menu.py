from __future__ import annotations

import os

from playwright.sync_api import FrameLocator
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from lunchbot.parse_menu import DayMenu, parse_menu_text
from lunchbot.timeutil import now_in
from lunchbot.welplan import COURSE_STATIONS

IFRAME = 'iframe[title="streamlitApp"]'
APP_READY = "text=BOB SSAFY"
MENU_READY = "text=메인 메뉴"
LOGIN_ERROR = "Not logged in"
WELMENU_HOST = "img-welmenu.welstory.com"

# BOB SSAFY 페이지 DOM 순서 (메인 4코너 → 추가배식대 → 마이보글)
BOB_STATION_ORDER = (
    COURSE_STATIONS["A1"],
    COURSE_STATIONS["AA"],
    COURSE_STATIONS["BB"],
    COURSE_STATIONS["CC"],
    COURSE_STATIONS["HH"],
    COURSE_STATIONS["DD"],
)


class BobssafyError(RuntimeError):
    pass


def default_bobssafy_timeout_ms() -> int:
    raw = os.getenv("BOBSSAFY_TIMEOUT_MS", "").strip()
    if raw:
        return int(raw)
    if os.getenv("CI"):
        return 45_000
    return 90_000


def _menu_poll_attempts() -> int:
    return 2 if os.getenv("CI") else 4


def is_welmenu_image_url(url: str) -> bool:
    return bool(url) and WELMENU_HOST in url and url.startswith("http")


def map_welmenu_images(urls: list[str]) -> dict[str, str]:
    """welmenu 이미지 URL 목록을 코너명 dict로 변환합니다."""
    photos: dict[str, str] = {}
    menu_urls = [url for url in urls if is_welmenu_image_url(url)]
    for station, url in zip(BOB_STATION_ORDER, menu_urls):
        photos[station] = url
    return photos


def apply_bobssafy_photos(menu: DayMenu, photos: dict[str, str], *, needs_photo) -> None:
    for item in [*menu.mains, *( [menu.ramen] if menu.ramen else [] ), *( [menu.extra] if menu.extra else [] )]:
        if item is None or not needs_photo(item):
            continue
        photo = photos.get(item.station, "")
        if photo:
            item.image_url = photo


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


def _load_app_frame(page, url: str, timeout_ms: int) -> FrameLocator:
    page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
    app = page.frame_locator(IFRAME)
    app.locator(APP_READY).first.wait_for(timeout=timeout_ms)
    return app


def _wait_for_menu(app: FrameLocator, page, timeout_ms: int) -> str:
    attempt_timeout = min(timeout_ms, 25_000 if os.getenv("CI") else timeout_ms)
    last_text = ""
    max_attempts = _menu_poll_attempts()
    for attempt in range(max_attempts):
        page.wait_for_timeout(1500 if os.getenv("CI") else 2500)
        last_text = app.locator("body").inner_text(timeout=attempt_timeout)
        if LOGIN_ERROR in last_text:
            raise BobssafyError(
                "BOB SSAFY가 메뉴 원본에 로그인하지 못한 상태입니다. "
                "사이트에서 메뉴가 보이는지 확인한 뒤 다시 실행해 주세요."
            )
        if "메인 메뉴" in last_text or "오늘의 메뉴" in last_text:
            try:
                app.locator(MENU_READY).first.wait_for(timeout=10_000)
            except PlaywrightTimeoutError:
                pass
            return last_text
        if attempt < max_attempts - 1:
            page.wait_for_timeout(2000 if os.getenv("CI") else 4000)
    raise BobssafyError("BOB SSAFY 페이지에서 메뉴 본문을 찾지 못했습니다.")


def _collect_image_urls(app: FrameLocator, timeout_ms: int) -> list[str]:
    urls: list[str] = []
    for img in app.locator("img").all():
        src = (img.get_attribute("src") or "").strip()
        if is_welmenu_image_url(src):
            urls.append(src)
    if not urls:
        raise BobssafyError("BOB SSAFY 페이지에서 welmenu 사진 URL을 찾지 못했습니다.")
    return urls


def fetch_menu_images(url: str, timeout_ms: int | None = None) -> dict[str, str]:
    limit = timeout_ms if timeout_ms is not None else default_bobssafy_timeout_ms()
    with sync_playwright() as playwright:
        browser, context = _browser_context(playwright)
        page = context.new_page()
        try:
            app = _load_app_frame(page, url, limit)
            _wait_for_menu(app, page, limit)
            page.wait_for_timeout(1000 if os.getenv("CI") else 2000)
            return map_welmenu_images(_collect_image_urls(app, limit))
        except PlaywrightTimeoutError as exc:
            raise BobssafyError(f"BOB SSAFY 페이지 로딩이 시간 초과되었습니다: {url}") from exc
        finally:
            context.close()
            browser.close()


def fetch_menu_page_text(url: str, timeout_ms: int = 90_000) -> str:
    with sync_playwright() as playwright:
        browser, context = _browser_context(playwright)
        page = context.new_page()
        try:
            app = _load_app_frame(page, url, timeout_ms)
            return _wait_for_menu(app, page, timeout_ms)
        except PlaywrightTimeoutError as exc:
            raise BobssafyError(f"BOB SSAFY 페이지 로딩이 시간 초과되었습니다: {url}") from exc
        finally:
            context.close()
            browser.close()


def fetch_today_menu(url: str, timezone: str = "Asia/Seoul") -> DayMenu:
    today = now_in(timezone).strftime("%Y-%m-%d")
    text = fetch_menu_page_text(url)
    return parse_menu_text(text, date_label=today)
