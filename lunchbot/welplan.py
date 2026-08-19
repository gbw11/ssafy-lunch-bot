"""Welplan(welplan.pmh.codes) — 메뉴 원본과 당일 사진 1차 소스."""

from __future__ import annotations

import hashlib
import html
import re
from datetime import datetime
from functools import lru_cache
from urllib.parse import quote

import requests

from lunchbot.models import DEFAULT_TIMEZONE, DayMenu, StationMenu, now_in

BASE_URL = "https://welplan.pmh.codes"
VENDOR = "welstory"
DEFAULT_RESTAURANT_ID = "REST000595"
DEFAULT_SLUG = "전기부산"
MAIN_HALL = "E32M"
LUNCH_MEAL_TIME_ID = "2"
TIMEOUT = 25

# 전기부산 점심 코너. 다른 방 급식봇과 같게 A1·AA·BB·CC(별미공방).
COURSE_STATIONS = {
    "A1": "브라운그릴",
    "AA": "동방식객",
    "BB": "모던키친",
    "CC": "별미공방",
    "DD": "마이보글",
    "HH": "추가배식대",
}
MAIN_ORDER = ("A1", "AA", "BB", "CC")
SECOND_ORDER = ("DD", "HH")

CAMPUS_RESTAURANT_CODES = {
    "서울": "REST000133",
    "역삼": "REST000133",
    "멀티캠퍼스": "REST000133",
    "전기부산": DEFAULT_RESTAURANT_ID,
    "삼성전기부산": DEFAULT_RESTAURANT_ID,
    "부울경": DEFAULT_RESTAURANT_ID,
}

OBJECT_RE = re.compile(r'\{id:"(?P<id>\d{8}-REST[0-9A-Z]+-[^"]+)",(?P<body>.*?)\};', re.S)
FIELD_RE = re.compile(r'(name|date|mealTimeId|hallNo|courseType|imageUrl|vendor):"([^"]*)"')
CALORIES_RE = re.compile(r"nutrition:\{calories:(\d+)")
PHOTO_STAMP_RE = re.compile(r"s(\d{14})")

# 실제 요리 사진이 아직 안 올라왔을 때 웰스토리가 대신 주는 JPEG.
PLACEHOLDER_MD5S = {"2a9fe28656e777f713319589de38f59f"}


def restaurant_code(campus: str, explicit: str = "") -> str:
    return explicit or CAMPUS_RESTAURANT_CODES.get(campus.strip(), "") or DEFAULT_RESTAURANT_ID


def restaurant_menu_url(restaurant_id: str, slug: str, date: datetime) -> str:
    encoded_slug = quote(slug, safe="")
    return f"{BASE_URL}/restaurants/{VENDOR}/{restaurant_id}/{encoded_slug}/{date:%Y%m%d}"


def is_placeholder_image_bytes(data: bytes) -> bool:
    if not data:
        return True
    return hashlib.md5(data).hexdigest() in PLACEHOLDER_MD5S


@lru_cache(maxsize=64)
def is_real_menu_image(url: str) -> bool:
    """플레이스홀더가 아닌 실제 사진인지 확인합니다(URL당 한 번만 내려받음)."""
    if not url:
        return False
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
    except requests.RequestException:
        return False
    return not is_placeholder_image_bytes(response.content)


def search_restaurants(query: str) -> list[dict]:
    response = requests.get(f"{BASE_URL}/proxy/search", params={"q": query}, timeout=20)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, list):
        raise RuntimeError("Welplan 검색 응답이 배열이 아닙니다.")
    return data


def _get_json(path: str, params: dict, *, required: bool = True):
    """required=False 면 실패해도 예외 대신 None을 돌려줍니다."""
    try:
        response = requests.get(
            f"{BASE_URL}{path}",
            params=params,
            headers={"Accept": "application/json", "Cache-Control": "no-store"},
            timeout=TIMEOUT,
        )
        if not response.ok:
            if not required:
                return None
            response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError):
        if required:
            raise
        return None


# ------------------------------------------------------------------ 당일 사진 병합


def _photo_stamp(url: str) -> str:
    match = PHOTO_STAMP_RE.search(url.rsplit("/", 1)[-1])
    return match.group(1) if match else ""


def _best_photo(urls: list[str], target_date: str) -> str:
    """같은 코너 사진이 여러 장이면 당일 파일 중 가장 늦게 찍힌 것을 고릅니다."""
    if not urls:
        return ""
    dated = [url for url in urls if _photo_stamp(url).startswith(target_date)]
    return max(dated or urls, key=lambda url: _photo_stamp(url) or "0")


def _menu_key(item: dict) -> str:
    """live API 응답과 카드를 짝지을 키. 양쪽 필드 이름이 달라 둘 다 봅니다."""
    return ":".join(
        str(value or "")
        for value in (
            item.get("vendor"),
            item.get("restaurantId") or item.get("restaurant_id"),
            item.get("date"),
            item.get("mealTimeId") or item.get("meal_time_id"),
            item.get("id") or item.get("menu_id"),
        )
    )


def fetch_live_menus(restaurant_id: str, date: datetime) -> list[dict]:
    payload = _get_json(
        "/api/menu/live",
        {
            "kind": "gallery",
            "date": f"{date:%Y%m%d}",
            "time": "all",
            "restaurantId": restaurant_id,
        },
        required=False,
    )
    menus = payload.get("menus") if isinstance(payload, dict) else None
    return menus if isinstance(menus, list) else []


def merge_live_images(cards: list[dict], live_menus: list[dict]) -> list[dict]:
    """live API 사진(당일 실사진)으로 카드의 레시피 사진을 갈아끼웁니다."""
    target_date = str(cards[0].get("date") or "") if cards else ""
    by_key = {
        _menu_key(menu): str(menu["imageUrl"]) for menu in live_menus if menu.get("imageUrl")
    }

    course_urls: dict[str, list[str]] = {}
    for menu in live_menus:
        if menu.get("hallNo") not in {MAIN_HALL, None, ""}:
            continue
        if target_date and str(menu.get("date") or "") != target_date:
            continue
        course = str(menu.get("courseType") or "")
        url = str(menu.get("imageUrl") or "")
        if course and url:
            course_urls.setdefault(course, []).append(url)
    by_course = {course: _best_photo(urls, target_date) for course, urls in course_urls.items()}

    merged: list[dict] = []
    for card in cards:
        candidates = [
            url
            for url in (by_key.get(_menu_key(card), ""), by_course.get(card["course_type"], ""))
            if url
        ]
        live_url = _best_photo(candidates, target_date)
        merged.append({**card, "image_url": live_url} if live_url else card)
    return merged


# --------------------------------------------------------------------- 메뉴 조회


def parse_lunch_cards(html_text: str, restaurant_id: str = DEFAULT_RESTAURANT_ID) -> list[dict]:
    """Welplan 페이지에 인라인된 JS 객체에서 본관 점심 코너 카드를 뽑습니다."""
    cards: list[dict] = []
    seen: set[str] = set()
    for match in OBJECT_RE.finditer(html_text):
        if restaurant_id not in match.group("id"):
            continue
        body = match.group("body")
        fields = dict(FIELD_RE.findall(body))
        if fields.get("mealTimeId") != LUNCH_MEAL_TIME_ID or fields.get("hallNo") != MAIN_HALL:
            continue
        course = fields.get("courseType", "")
        if course not in COURSE_STATIONS or course in seen:
            continue
        calories = [int(value) for value in CALORIES_RE.findall(body)]
        cards.append(
            {
                "menu_id": match.group("id"),
                "name": html.unescape(fields.get("name", "")),
                "course_type": course,
                "station": COURSE_STATIONS[course],
                "image_url": fields.get("imageUrl", ""),
                "calories": calories[-1] if calories else 0,
                "hall_no": MAIN_HALL,
                "vendor": fields.get("vendor", VENDOR),
                "restaurant_id": restaurant_id,
                "date": fields.get("date", ""),
                "meal_time_id": LUNCH_MEAL_TIME_ID,
            }
        )
        seen.add(course)
    return cards


def fetch_course_detail(
    restaurant_id: str,
    date: datetime,
    hall_no: str,
    course_type: str,
) -> list[dict]:
    payload = _get_json(
        f"/proxy/{restaurant_id}/menus/detail",
        {
            "date": f"{date:%Y%m%d}",
            "mealTimeId": LUNCH_MEAL_TIME_ID,
            "hallNo": hall_no,
            "courseType": course_type,
            "nutrient": "1",
        },
    )
    if not isinstance(payload, list):
        return []
    rows: list[dict] = []
    for row in payload:
        name = html.unescape(str(row.get("name") or "")).strip()
        if not name:
            continue
        calories = int((row.get("nutrition") or {}).get("calories") or 0)
        rows.append({"name": name, "calories": calories})
    return rows


def _ramen_card(restaurant_id: str, date: datetime) -> dict | None:
    """마이보글(DD)은 카드로 안 나오는 날이 있어 상세 API로 직접 만듭니다."""
    rows = fetch_course_detail(restaurant_id, date, MAIN_HALL, "DD")
    if not rows:
        return None
    day = f"{date:%Y%m%d}"
    return {
        "menu_id": f"{day}-{restaurant_id}-{MAIN_HALL}-DD",
        "name": rows[0]["name"],
        "course_type": "DD",
        "station": COURSE_STATIONS["DD"],
        "image_url": "",
        "calories": sum(row["calories"] for row in rows),
        "hall_no": MAIN_HALL,
        "vendor": VENDOR,
        "restaurant_id": restaurant_id,
        "date": day,
        "meal_time_id": LUNCH_MEAL_TIME_ID,
    }


def cards_to_day_menu(
    cards: list[dict],
    details: dict[str, list[dict]],
    date_label: str,
) -> DayMenu:
    by_course = {card["course_type"]: card for card in cards}
    menu = DayMenu(date_label=date_label)
    for course in (*MAIN_ORDER, *SECOND_ORDER):
        card = by_course.get(course)
        if not card:
            continue
        rows = details.get(course) or [{"name": card["name"], "calories": card["calories"]}]
        names = [row["name"] for row in rows]
        calories = card["calories"]
        if course == "DD" and not calories:
            calories = sum(row["calories"] for row in rows)
        station = StationMenu(
            station=card["station"],
            name=names[0],
            kcal=f"{calories:,}kcal" if calories > 0 else "",
            items=names[1:],
            image_url=card["image_url"],
            course_type=course,
        )
        if course in MAIN_ORDER:
            menu.mains.append(station)
        elif course == "DD":
            menu.ramen = station
        else:
            menu.extra = station
    return menu


def fetch_today_menu(
    restaurant_id: str = DEFAULT_RESTAURANT_ID,
    slug: str = DEFAULT_SLUG,
    timezone: str = DEFAULT_TIMEZONE,
) -> DayMenu:
    today = now_in(timezone)
    response = requests.get(
        restaurant_menu_url(restaurant_id, slug, today),
        headers={"Accept": "text/html"},
        timeout=30,
    )
    response.raise_for_status()
    response.encoding = "utf-8"

    cards = parse_lunch_cards(response.text, restaurant_id)
    if not any(card["course_type"] == "DD" for card in cards):
        ramen = _ramen_card(restaurant_id, today)
        if ramen:
            cards.append(ramen)

    live_menus = fetch_live_menus(restaurant_id, today)
    if live_menus:
        cards = merge_live_images(cards, live_menus)

    details = {
        card["course_type"]: fetch_course_detail(
            restaurant_id, today, card["hall_no"], card["course_type"]
        )
        for card in cards
    }
    return cards_to_day_menu(cards, details, f"{today:%Y-%m-%d}")
