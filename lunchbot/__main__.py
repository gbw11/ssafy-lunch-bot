from __future__ import annotations

import argparse
import json
import sys

from lunchbot.config import load_settings
from lunchbot.format_message import format_mattermost_message
from lunchbot.menu import fetch_today_menu
from lunchbot.notify import send_message
from lunchbot.timeutil import now_in
from lunchbot.welplan import (
    DEFAULT_RESTAURANT_ID,
    DEFAULT_SLUG,
    restaurant_menu_url,
    search_restaurants,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="전기부산 급식표를 Mattermost로 보냅니다.")
    parser.add_argument("--dry-run", action="store_true", help="메시지만 출력하고 전송하지 않습니다.")
    parser.add_argument(
        "--list-restaurants",
        metavar="QUERY",
        nargs="?",
        const="전기부산",
        help="Welplan에서 식당을 검색합니다. 기본 검색어: 전기부산",
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
    args = parser.parse_args(argv)
    settings = load_settings()

    if args.test_welstory:
        from lunchbot.welstory import (
            WelstoryError,
            authenticated_session,
            fetch_lunch_meals,
            meal_photo_url,
            resolve_restaurant_code,
            verify_session,
        )

        restaurant_id = settings.welstory_restaurant_code or resolve_restaurant_code(
            settings.welstory_campus, settings.welstory_restaurant_code
        ) or DEFAULT_RESTAURANT_ID
        try:
            session = authenticated_session(
                username=settings.welstory_username,
                password=settings.welstory_password,
                remember_me=settings.welstory_remember_me,
                jsessionid=settings.welstory_jsessionid,
            )
            verify_session(session, restaurant_id)
            meals = fetch_lunch_meals(session, restaurant_id, timezone=settings.timezone)
        except WelstoryError as exc:
            print(f"웰스토리 연결 실패: {exc}", file=sys.stderr)
            return 1
        print(f"웰스토리 연결 OK (메뉴 {len(meals)}개)")
        for meal in meals[:12]:
            station = meal.get("courseTxt") or meal.get("course") or "?"
            photo = meal_photo_url(meal)
            tail = photo.split("/")[-1] if photo else "(사진 없음)"
            print(f"  {station}: {tail}")
        return 0

    if args.test_bobssafy:
        from lunchbot.fetch_menu import BobssafyError, fetch_menu_images

        try:
            photos = fetch_menu_images(settings.bobssafy_url)
        except BobssafyError as exc:
            print(f"BOB SSAFY 연결 실패: {exc}", file=sys.stderr)
            return 1
        print(f"BOB SSAFY 연결 OK (사진 {len(photos)}개)")
        for station, url in photos.items():
            tail = url.split("/")[-1] if url else "(사진 없음)"
            print(f"  {station}: {tail}")
        return 0

    if args.list_restaurants is not None:
        results = search_restaurants(args.list_restaurants)
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return 0

    menu = fetch_today_menu(settings)
    if not menu.has_content:
        print("오늘 메뉴가 없어 메시지를 보내지 않습니다.", file=sys.stderr)
        return 0

    today = now_in(settings.timezone)
    source_url = restaurant_menu_url(
        settings.welstory_restaurant_code or DEFAULT_RESTAURANT_ID,
        settings.welstory_campus or DEFAULT_SLUG,
        today,
    )
    message = format_mattermost_message(menu, source_url)
    print(message)
    if args.dry_run:
        return 0

    method = send_message(settings, message)
    print(f"\n전송 완료 ({method})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
