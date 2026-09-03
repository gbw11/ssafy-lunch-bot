"""CLI 진입점: 메뉴를 모아 Mattermost로 보냅니다."""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections.abc import Callable

import requests

from lunchbot import mealcloud, welplan, welstory
from lunchbot.config import Settings, load_settings
from lunchbot.message import format_message
from lunchbot.models import DayMenu, StationMenu, now_in
from lunchbot.notify import send_message

# (로그에 쓸 이름, 사진 조회, 그 소스가 내는 예외)
PhotoSource = tuple[str, Callable[[], dict[str, str]], type[Exception]]

PHOTO_HINT = (
    " 사진 소스(Welplan live API / welstory-meal.cloud)에 아직 실사진이 없거나 "
    "코너 이름·메뉴명이 달라 짝이 안 맞은 경우입니다."
)


def _log(message: str) -> None:
    print(message, file=sys.stderr)


def _needs_photo(item: StationMenu) -> bool:
    """사진이 없거나, 요리 사진 대신 플레이스홀더가 걸려 있으면 채워야 합니다."""
    return not welplan.is_real_menu_image(item.image_url)


def _warn_missing_photos(menu: DayMenu) -> None:
    missing = []
    for item in menu.stations:
        if _needs_photo(item):
            item.image_url = ""  # 플레이스홀더 사진은 아예 빼고 보냅니다.
            missing.append(item.station)
    if not missing:
        return
    _log("당일 사진이 없는 코너: " + ", ".join(missing) + " —" + PHOTO_HINT)


def _wait_for_lunch_photos(
    menu: DayMenu,
    settings: Settings,
    restaurant_code: str,
    sources: list[PhotoSource],
) -> None:
    """실제 점심 사진은 배식 직전에야 올라옵니다. 그때까지 live API를 다시 봅니다."""
    deadline = time.monotonic() + settings.photo_wait_seconds
    waited = 0
    while any(_needs_photo(item) for item in menu.stations):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            if waited:
                _log(f"{waited // 60}분을 기다렸지만 점심 사진이 다 올라오지 않아 그대로 보냅니다.")
            return
        pause = int(min(settings.photo_poll_seconds, remaining))
        if waited == 0:
            _log("아직 점심 사진이 올라오지 않아 기다립니다. (최대 "
                 f"{settings.photo_wait_seconds // 60}분)")
        time.sleep(pause)
        waited += pause
        # welplan live API 는 죽는 날이 잦고(타임아웃 25초) 그동안 루프가 멈춥니다.
        # 빠르고 안정적인 소스를 먼저 보고, 남은 코너만 live API 로 재조회합니다.
        _fill_from_sources(menu, sources, quiet=True)
        if not any(_needs_photo(item) for item in menu.stations):
            break
        try:
            photos = welplan.fetch_live_photos(restaurant_code, now_in(settings.timezone))
        except requests.RequestException as exc:
            _log(f"사진 재조회 실패(계속 시도합니다): {exc}")
        else:
            menu.fill_photos(photos, _needs_photo)
    if waited:
        _log(f"{waited // 60}분 {waited % 60}초 만에 점심 사진이 올라왔습니다.")


def _photo_sources(settings: Settings, restaurant_code: str) -> list[PhotoSource]:
    """사진 소스를 시도 순서대로.

    브라우저에서 받은 accessToken·쿠키가 있으면 원본(웰스토리 API)을 폴백보다 먼저 봅니다.
    그게 없이 ID/PW만 있으면 Incapsula WAF에 막혀 거의 실패하므로 맨 뒤로 밀어
    폴백이 먼저 사진을 채우게 둡니다.
    """
    welstory_source: PhotoSource = (
        f"웰스토리({welstory.auth_mode(settings)})",
        lambda: welstory.fetch_photos(settings, restaurant_code),
        welstory.WelstoryError,
    )
    sources: list[PhotoSource] = []
    if settings.has_welstory_session:
        sources.append(welstory_source)
    if settings.mealcloud_enabled:
        sources.append(
            (
                "welstory-meal.cloud",
                lambda: mealcloud.fetch_photos(settings.mealcloud_url, settings.timezone),
                mealcloud.MealCloudError,
            )
        )
    if settings.has_welstory_login and not settings.has_welstory_session:
        sources.append(welstory_source)
    return sources


def _fill_from_sources(menu: DayMenu, sources: list[PhotoSource], *, quiet: bool = False) -> None:
    for label, fetch, error in sources:
        if not any(_needs_photo(item) for item in menu.stations):
            return
        try:
            photos = fetch()
        except error as exc:  # 소스 하나가 죽어도 다음 소스로 넘어갑니다.
            if not quiet:  # 대기 루프에서 매분 부를 때는 조용히 넘어갑니다.
                _log(f"{label} 사진을 가져오지 못했습니다: {exc}")
            continue
        menu.fill_photos(photos, _needs_photo)


def build_today_menu(settings: Settings) -> DayMenu:
    """메뉴는 Welplan에서, 빠진 사진은 `_photo_sources` 순서대로 채웁니다."""
    restaurant_code = welplan.restaurant_code(
        settings.welstory_campus, settings.welstory_restaurant_code
    )
    menu = welplan.fetch_today_menu(
        restaurant_id=restaurant_code,
        slug=settings.welstory_campus or welplan.DEFAULT_SLUG,
        timezone=settings.timezone,
    )
    sources = _photo_sources(settings, restaurant_code)
    _wait_for_lunch_photos(menu, settings, restaurant_code, sources)
    _fill_from_sources(menu, sources)
    _warn_missing_photos(menu)
    return menu


def _report_photos(label: str, photos: dict[str, str]) -> int:
    print(f"{label} 연결 OK (사진 {len(photos)}개)")
    for station, url in photos.items():
        print(f"  {station}: {url.rsplit('/', 1)[-1] if url else '(사진 없음)'}")
    return 0


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="전기부산 급식표를 Mattermost로 보냅니다.")
    parser.add_argument(
        "--dry-run", action="store_true", help="메시지만 출력하고 전송하지 않습니다."
    )
    parser.add_argument(
        "--list-restaurants",
        metavar="QUERY",
        nargs="?",
        const=welplan.DEFAULT_SLUG,
        help=f"Welplan에서 식당을 검색합니다. 기본 검색어: {welplan.DEFAULT_SLUG}",
    )
    parser.add_argument(
        "--test-welstory",
        action="store_true",
        help="웰스토리 인증과 당일 사진 URL 조회만 테스트합니다.",
    )
    parser.add_argument(
        "--test-mealcloud",
        action="store_true",
        help="welstory-meal.cloud에서 코너별 사진 URL 조회만 테스트합니다.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    settings = load_settings()

    if args.test_welstory:
        code = welplan.restaurant_code(
            settings.welstory_campus, settings.welstory_restaurant_code
        )
        _log(f"웰스토리 인증 경로: {welstory.auth_mode(settings)}")
        try:
            photos = welstory.fetch_photos(settings, code)
        except welstory.WelstoryError as exc:
            _log(f"웰스토리 연결 실패: {exc}")
            return 1
        return _report_photos("웰스토리", photos)

    if args.test_mealcloud:
        try:
            photos = mealcloud.fetch_photos(settings.mealcloud_url, settings.timezone)
        except mealcloud.MealCloudError as exc:
            _log(f"welstory-meal.cloud 연결 실패: {exc}")
            return 1
        return _report_photos("welstory-meal.cloud", photos)

    if args.list_restaurants is not None:
        results = welplan.search_restaurants(args.list_restaurants)
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return 0

    menu = build_today_menu(settings)
    if not menu.has_content:
        _log("오늘 메뉴가 없어 메시지를 보내지 않습니다.")
        return 0

    message = format_message(menu)
    print(message)
    if args.dry_run:
        return 0

    result = send_message(settings, message)
    _log(f"\n전송 완료 ({result})")
    return 0 if result.ok else 1  # 일부 방이 실패하면 Actions에서도 실패로 보이게 합니다.


if __name__ == "__main__":
    raise SystemExit(main())
