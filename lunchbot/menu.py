from __future__ import annotations

import sys

from lunchbot.config import Settings
from lunchbot.parse_menu import DayMenu
from lunchbot.welplan import (
    DEFAULT_RESTAURANT_ID,
    DEFAULT_SLUG,
    fetch_today_menu_from_welplan,
    is_real_menu_image,
)
from lunchbot.welstory import (
    WelstoryError,
    apply_meal_photos,
    authenticated_session,
    fetch_lunch_meals,
    resolve_restaurant_code,
    verify_session,
)


def _photo_hint(settings: Settings) -> str:
    if settings.has_welstory_login:
        return (
            " WELLSTORY_USERNAME/PASSWORD(웰스토리 앱 계정)를 확인하세요. "
            "로그인을 여러 번 시도하면 계정이 30분간 잠길 수 있습니다."
        )
    return " .env에 WELLSTORY_USERNAME/PASSWORD(웰스토리 앱 아이디/비번)를 넣어 주세요."


def _warn_missing_photos(menu: DayMenu, settings: Settings) -> None:
    missing = []
    for item in [*menu.mains, *( [menu.ramen] if menu.ramen else [] ), *( [menu.extra] if menu.extra else [] )]:
        if not item.image_url:
            missing.append(item.station)
        elif not is_real_menu_image(item.image_url):
            item.image_url = ""
            missing.append(item.station)
    if not missing:
        return
    print(
        "당일 사진이 없는 코너: "
        + ", ".join(missing)
        + " —"
        + _photo_hint(settings),
        file=sys.stderr,
    )


def fetch_today_menu(settings: Settings) -> DayMenu:
    restaurant_id = settings.welstory_restaurant_code or resolve_restaurant_code(
        settings.welstory_campus, settings.welstory_restaurant_code
    ) or DEFAULT_RESTAURANT_ID
    slug = settings.welstory_campus or DEFAULT_SLUG
    menu = fetch_today_menu_from_welplan(
        restaurant_id=restaurant_id,
        slug=slug,
        timezone=settings.timezone,
    )
    if settings.has_welstory:
        try:
            session = authenticated_session(
                username=settings.welstory_username,
                password=settings.welstory_password,
                remember_me=settings.welstory_remember_me,
                jsessionid=settings.welstory_jsessionid,
            )
            verify_session(session, restaurant_id)
            meals = fetch_lunch_meals(session, restaurant_id, timezone=settings.timezone)
            apply_meal_photos(menu, meals)
        except WelstoryError as exc:
            print(f"웰스토리 당일 사진을 가져오지 못했습니다: {exc}", file=sys.stderr)
        _warn_missing_photos(menu, settings)
    else:
        _warn_missing_photos(menu, settings)
    return menu
