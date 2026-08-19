"""CLI 진입점: 메뉴를 모아 Mattermost로 보냅니다."""

from __future__ import annotations

import argparse
import json
import sys

from lunchbot import welplan, welstory
from lunchbot.config import Settings, load_settings
from lunchbot.message import format_message
from lunchbot.models import DayMenu, StationMenu
from lunchbot.notify import send_message

PHOTO_HINT_LOGIN = (
    " WELLSTORY_USERNAME/PASSWORD(웰스토리 앱 계정)를 확인하세요. "
    "로그인을 여러 번 시도하면 계정이 30분간 잠길 수 있습니다."
)
PHOTO_HINT_NO_LOGIN = (
    " .env에 WELLSTORY_USERNAME/PASSWORD(웰스토리 앱 아이디/비번)를 넣어 주세요."
)


def _log(message: str) -> None:
    print(message, file=sys.stderr)


def _needs_photo(item: StationMenu) -> bool:
    """사진이 없거나, 요리 사진 대신 플레이스홀더가 걸려 있으면 채워야 합니다."""
    return not welplan.is_real_menu_image(item.image_url)


def _warn_missing_photos(menu: DayMenu, settings: Settings) -> None:
    missing = []
    for item in menu.stations:
        if _needs_photo(item):
            item.image_url = ""  # 플레이스홀더 사진은 아예 빼고 보냅니다.
            missing.append(item.station)
    if not missing:
        return
    hint = PHOTO_HINT_LOGIN if settings.has_welstory_login else PHOTO_HINT_NO_LOGIN
    _log("당일 사진이 없는 코너: " + ", ".join(missing) + " —" + hint)


def _fill_from_bobssafy(menu: DayMenu, settings: Settings) -> None:
    from lunchbot.bobssafy import BobssafyError, fetch_photos  # playwright는 필요할 때만

    try:
        photos = fetch_photos(settings.bobssafy_url)
    except BobssafyError as exc:
        _log(f"BOB SSAFY 사진을 가져오지 못했습니다: {exc}")
        return
    menu.fill_photos(photos, _needs_photo)


def _fill_from_welstory(menu: DayMenu, settings: Settings, restaurant_code: str) -> None:
    try:
        photos = welstory.fetch_photos(settings, restaurant_code)
    except welstory.WelstoryError as exc:
        _log(f"웰스토리 당일 사진을 가져오지 못했습니다: {exc}")
        return
    menu.fill_photos(photos, _needs_photo)


def build_today_menu(settings: Settings) -> DayMenu:
    """메뉴는 Welplan에서, 빠진 사진은 BOB SSAFY → 웰스토리 순으로 채웁니다."""
    restaurant_code = welplan.restaurant_code(
        settings.welstory_campus, settings.welstory_restaurant_code
    )
    menu = welplan.fetch_today_menu(
        restaurant_id=restaurant_code,
        slug=settings.welstory_campus or welplan.DEFAULT_SLUG,
        timezone=settings.timezone,
    )
    if settings.bobssafy_enabled and any(_needs_photo(item) for item in menu.stations):
        _fill_from_bobssafy(menu, settings)
    if settings.has_welstory and any(_needs_photo(item) for item in menu.stations):
        _fill_from_welstory(menu, settings, restaurant_code)
    _warn_missing_photos(menu, settings)
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
        "--test-bobssafy",
        action="store_true",
        help="BOB SSAFY에서 코너별 사진 URL 조회만 테스트합니다.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    settings = load_settings()

    if args.test_welstory:
        code = welplan.restaurant_code(
            settings.welstory_campus, settings.welstory_restaurant_code
        )
        try:
            photos = welstory.fetch_photos(settings, code)
        except welstory.WelstoryError as exc:
            _log(f"웰스토리 연결 실패: {exc}")
            return 1
        return _report_photos("웰스토리", photos)

    if args.test_bobssafy:
        from lunchbot.bobssafy import BobssafyError, fetch_photos

        try:
            photos = fetch_photos(settings.bobssafy_url)
        except BobssafyError as exc:
            _log(f"BOB SSAFY 연결 실패: {exc}")
            return 1
        return _report_photos("BOB SSAFY", photos)

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

    _log(f"\n전송 완료 ({send_message(settings, message)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
