from __future__ import annotations

import re
from datetime import datetime

import requests

from lunchbot.parse_menu import DayMenu, StationMenu
from lunchbot.timeutil import now_in

BASE_URL = "https://welplus.welstory.com"
MEAL_TYPE_LUNCH = "2"
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Referer": f"{BASE_URL}/",
}

CAMPUS_RESTAURANT_CODES = {
    "서울": "REST000133",
    "역삼": "REST000133",
    "멀티캠퍼스": "REST000133",
    "전기부산": "REST000595",
    "삼성전기부산": "REST000595",
    "부울경": "REST000595",
}


class WelstoryError(RuntimeError):
    pass


def _clean_api_message(message: str) -> str:
    text = re.sub(r"<[^>]+>", " ", message or "")
    return " ".join(text.split())


def _parse_login_response(response: requests.Response) -> dict:
    try:
        payload = response.json()
    except ValueError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _session_with_cookies(*, remember_me: str = "", jsessionid: str = "") -> requests.Session:
    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)
    if remember_me:
        session.cookies.set("remember-me", remember_me, domain=".welstory.com", path="/")
    if jsessionid:
        session.cookies.set("JSESSIONID", jsessionid, domain=".welstory.com", path="/")
    return session


def login(username: str, password: str) -> requests.Session:
    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)
    session.get(f"{BASE_URL}/", timeout=20)

    attempts = [
        {"params": {"username": username, "password": password, "remember-me": "true"}},
        {"data": {"username": username, "password": password, "remember-me": "true"}},
    ]
    last_message = ""
    last_code: int | str | None = None
    for kwargs in attempts:
        response = session.post(f"{BASE_URL}/login", timeout=20, **kwargs)
        payload = _parse_login_response(response)
        last_message = _clean_api_message(str(payload.get("message") or ""))
        last_code = payload.get("code")
        if session.cookies.get("JSESSIONID"):
            return session
        if payload.get("code") in {0, "0"} and payload.get("data"):
            return session

    hint = (
        "WELLSTORY_USERNAME/PASSWORD에 웰스토리 앱 계정을 넣어 주세요. "
        "웹사이트 로그인 화면은 없어도 API 로그인은 가능합니다."
    )
    if last_code in {-112, "-112"}:
        hint = (
            "로그인 시도가 많아 계정이 잠겼습니다. 30분 후 다시 시도해 주세요. "
            "그동안 봇을 반복 실행하지 마세요."
        )
    detail = f" ({last_message})" if last_message else ""
    raise WelstoryError(f"웰스토리 로그인에 실패했습니다.{detail} {hint}")


def authenticated_session(
    *,
    username: str = "",
    password: str = "",
    remember_me: str = "",
    jsessionid: str = "",
) -> requests.Session:
    if remember_me or jsessionid:
        return _session_with_cookies(remember_me=remember_me, jsessionid=jsessionid)
    if username and password:
        return login(username, password)
    raise WelstoryError(
        "웰스토리 인증 정보가 없습니다. WELLSTORY_USERNAME/PASSWORD 또는 "
        "WELLSTORY_REMEMBER_ME 를 .env 에 넣어 주세요."
    )


def verify_session(session: requests.Session, restaurant_code: str) -> None:
    response = session.get(
        f"{BASE_URL}/api/meal",
        params={
            "menuDt": now_in("Asia/Seoul").strftime("%Y%m%d"),
            "menuMealType": MEAL_TYPE_LUNCH,
            "restaurantCode": restaurant_code,
        },
        timeout=20,
    )
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


def resolve_restaurant_code(campus: str, explicit_code: str = "") -> str:
    if explicit_code:
        return explicit_code
    return CAMPUS_RESTAURANT_CODES.get(campus.strip(), "")


def fetch_lunch_meals(
    session: requests.Session,
    restaurant_code: str,
    day: datetime | None = None,
    timezone: str = "Asia/Seoul",
) -> list[dict]:
    if not restaurant_code:
        raise WelstoryError(
            "식당 코드가 없습니다. WELLSTORY_RESTAURANT_CODE 또는 "
            "WELLSTORY_CAMPUS(예: 서울)를 설정하세요."
        )
    target = day or now_in(timezone)
    menu_dt = target.strftime("%Y%m%d")
    response = session.get(
        f"{BASE_URL}/api/meal",
        params={
            "menuDt": menu_dt,
            "menuMealType": MEAL_TYPE_LUNCH,
            "restaurantCode": restaurant_code,
        },
        timeout=20,
    )
    response.raise_for_status()
    if response.headers.get("wp-error") == "login" or not response.content:
        raise WelstoryError(
            "웰스토리 로그인이 필요합니다. WELLSTORY_REMEMBER_ME 또는 "
            "WELLSTORY_USERNAME / WELLSTORY_PASSWORD 를 확인해 주세요."
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
    """다른 SSAFY 급식봇과 같이 photoUrl + photoCd 로 당일 사진을 만듭니다."""
    base = str(meal.get("photoUrl") or "").strip()
    code = str(meal.get("photoCd") or "").strip()
    if not base:
        return ""
    photo = f"{base}{code}"
    if not photo.startswith("http"):
        return ""
    return photo


def apply_meal_photos(menu: DayMenu, meals: list[dict]) -> DayMenu:
    by_course: dict[str, str] = {}
    by_station: dict[str, str] = {}
    for meal in meals:
        photo = meal_photo_url(meal)
        if not photo:
            continue
        course = str(meal.get("menuCourseType") or "").strip()
        station = str(meal.get("courseTxt") or meal.get("course") or "").split(":")[-1].strip()
        if course:
            by_course[course] = photo
        if station:
            by_station[station] = photo

    def fill(item: StationMenu | None) -> None:
        if item is None:
            return
        photo = by_course.get(item.course_type) or by_station.get(item.station)
        if photo:
            item.image_url = photo

    for item in menu.mains:
        fill(item)
    fill(menu.extra)
    fill(menu.ramen)
    return menu


def _split_items(raw: str) -> list[str]:
    if not raw:
        return []
    return [part.strip() for part in re.split(r"[,/\n]", raw) if part.strip()]


def meals_to_day_menu(meals: list[dict], date_label: str) -> DayMenu:
    mains: list[StationMenu] = []
    extra: StationMenu | None = None
    ramen: StationMenu | None = None

    for meal in meals:
        station = str(meal.get("courseTxt") or meal.get("course") or "코너").strip()
        name = str(meal.get("menuName") or "").strip()
        kcal = str(meal.get("sumKcal") or "").strip()
        if kcal and "kcal" not in kcal.lower():
            kcal = f"{kcal}kcal"
        items = _split_items(str(meal.get("subMenuTxt") or meal.get("subMenu") or ""))
        parsed = StationMenu(
            station=station.split(":")[-1].strip() or station,
            name=name or station,
            kcal=kcal,
            items=items,
            image_url=meal_photo_url(meal),
            course_type=str(meal.get("menuCourseType") or "").strip(),
        )

        joined = f"{station} {name}"
        if "라면" in joined or "마이보글" in joined:
            ramen = parsed
        elif "추가" in joined or "배식" in joined:
            extra = parsed
        else:
            mains.append(parsed)

    return DayMenu(date_label=date_label, mains=mains, extra=extra, ramen=ramen)


def fetch_today_menu_from_welstory(
    username: str,
    password: str,
    restaurant_code: str,
    timezone: str = "Asia/Seoul",
    *,
    remember_me: str = "",
    jsessionid: str = "",
) -> DayMenu:
    session = authenticated_session(
        username=username,
        password=password,
        remember_me=remember_me,
        jsessionid=jsessionid,
    )
    verify_session(session, restaurant_code)
    today = now_in(timezone)
    meals = fetch_lunch_meals(session, restaurant_code, today, timezone)
    return meals_to_day_menu(meals, today.strftime("%Y-%m-%d"))
