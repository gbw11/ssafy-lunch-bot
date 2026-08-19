"""웰스토리플러스 API — 당일 코너 사진 폴백."""

from __future__ import annotations

import re

import requests

from lunchbot.config import Settings
from lunchbot.models import now_in

BASE_URL = "https://welplus.welstory.com"
MEAL_TYPE_LUNCH = "2"
LOCKED_CODES = {-112, "-112"}
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Referer": f"{BASE_URL}/",
}

LOGIN_HINT = (
    "WELLSTORY_USERNAME/PASSWORD에 웰스토리 앱 계정을 넣어 주세요. "
    "웹사이트 로그인 화면은 없어도 API 로그인은 가능합니다."
)
LOCKED_HINT = (
    "로그인 시도가 많아 계정이 잠겼습니다. 30분 후 다시 시도해 주세요. "
    "그동안 봇을 반복 실행하지 마세요."
)


class WelstoryError(RuntimeError):
    pass


def _new_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(HEADERS)
    return session


def _login(username: str, password: str) -> requests.Session:
    session = _new_session()
    session.get(f"{BASE_URL}/", timeout=20)

    credentials = {"username": username, "password": password, "remember-me": "true"}
    last_message = ""
    last_code: int | str | None = None
    # 서버가 날에 따라 query string / form body 중 한쪽만 받습니다.
    for kwargs in ({"params": credentials}, {"data": credentials}):
        response = session.post(f"{BASE_URL}/login", timeout=20, **kwargs)
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        last_message = " ".join(re.sub(r"<[^>]+>", " ", str(payload.get("message") or "")).split())
        last_code = payload.get("code")
        if session.cookies.get("JSESSIONID"):
            return session
        if last_code in {0, "0"} and payload.get("data"):
            return session

    detail = f" ({last_message})" if last_message else ""
    hint = LOCKED_HINT if last_code in LOCKED_CODES else LOGIN_HINT
    raise WelstoryError(f"웰스토리 로그인에 실패했습니다.{detail} {hint}")


def _authenticated_session(settings: Settings) -> requests.Session:
    if settings.welstory_remember_me or settings.welstory_jsessionid:
        session = _new_session()
        for name, value in (
            ("remember-me", settings.welstory_remember_me),
            ("JSESSIONID", settings.welstory_jsessionid),
        ):
            if value:
                session.cookies.set(name, value, domain=".welstory.com", path="/")
        return session
    if settings.has_welstory_login:
        return _login(settings.welstory_username, settings.welstory_password)
    raise WelstoryError(
        "웰스토리 인증 정보가 없습니다. WELLSTORY_USERNAME/PASSWORD 또는 "
        "WELLSTORY_REMEMBER_ME 를 .env 에 넣어 주세요."
    )


def fetch_lunch_meals(
    session: requests.Session,
    restaurant_code: str,
    timezone: str = "Asia/Seoul",
) -> list[dict]:
    response = session.get(
        f"{BASE_URL}/api/meal",
        params={
            "menuDt": f"{now_in(timezone):%Y%m%d}",
            "menuMealType": MEAL_TYPE_LUNCH,
            "restaurantCode": restaurant_code,
        },
        timeout=20,
    )
    response.raise_for_status()
    if response.headers.get("wp-error") == "login" or not response.content:
        raise WelstoryError(
            "웰스토리 세션이 만료되었거나 유효하지 않습니다. "
            "welplus.welstory.com 에 다시 로그인한 뒤 remember-me 쿠키를 갱신해 주세요."
        )
    try:
        payload = response.json()
    except ValueError as exc:
        raise WelstoryError("웰스토리 메뉴 응답이 JSON이 아닙니다.") from exc
    meals = (payload.get("data") or {}).get("mealList") or []
    if not isinstance(meals, list):
        raise WelstoryError("웰스토리 메뉴 응답 형식이 예상과 다릅니다.")
    return meals


def meal_photo_url(meal: dict) -> str:
    """다른 SSAFY 급식봇과 같이 photoUrl + photoCd 로 당일 사진 URL을 만듭니다."""
    base = str(meal.get("photoUrl") or "").strip()
    if not base:
        return ""
    photo = base + str(meal.get("photoCd") or "").strip()
    return photo if photo.startswith("http") else ""


def meal_photos(meals: list[dict]) -> dict[str, str]:
    """코너코드(menuCourseType)와 코너명 양쪽으로 찾을 수 있는 사진 목록."""
    photos: dict[str, str] = {}
    for meal in meals:
        photo = meal_photo_url(meal)
        if not photo:
            continue
        course = str(meal.get("menuCourseType") or "").strip()
        station = str(meal.get("courseTxt") or meal.get("course") or "").split(":")[-1].strip()
        for key in (course, station):
            if key:
                photos[key] = photo
    return photos


def fetch_photos(settings: Settings, restaurant_code: str) -> dict[str, str]:
    session = _authenticated_session(settings)
    meals = fetch_lunch_meals(session, restaurant_code, settings.timezone)
    return meal_photos(meals)
