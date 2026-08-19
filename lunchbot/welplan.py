from __future__ import annotations

import hashlib
import html
import re
from datetime import datetime
from urllib.parse import quote

import requests

from lunchbot.parse_menu import DayMenu, StationMenu
from lunchbot.timeutil import now_in

WELPLAN_BASE = "https://welplan.pmh.codes"
DEFAULT_VENDOR = "welstory"
DEFAULT_RESTAURANT_ID = "REST000595"
DEFAULT_SLUG = "전기부산"
MAIN_HALL = "E32M"
LUNCH_MEAL_TIME_ID = "2"

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

OBJECT_RE = re.compile(
    r'\{id:"(?P<id>\d{8}-REST[0-9A-Z]+-[^"]+)",(?P<body>.*?)\};',
    re.S,
)
FIELD_RE = re.compile(r'(name|date|mealTimeId|hallNo|courseType|imageUrl|vendor):"([^"]*)"')
CALORIES_RE = re.compile(r"nutrition:\{calories:(\d+)")
LIVE_TIMEOUT = 25
# Welstory serves this JPEG when the actual dish photo is not uploaded yet.
PLACEHOLDER_MD5S = {
    "2a9fe28656e777f713319589de38f59f",
}


def _menu_key(item: dict) -> str:
    restaurant_id = item.get("restaurantId") or item.get("restaurant_id") or ""
    meal_time = item.get("mealTimeId") or item.get("meal_time_id") or ""
    menu_id = item.get("id") or item.get("menu_id") or ""
    return ":".join(
        [
            str(item.get("vendor") or ""),
            str(restaurant_id),
            str(item.get("date") or ""),
            str(meal_time),
            str(menu_id),
        ]
    )


def is_placeholder_image_bytes(data: bytes) -> bool:
    if not data:
        return True
    return hashlib.md5(data).hexdigest() in PLACEHOLDER_MD5S


def is_real_menu_image(url: str) -> bool:
    if not url:
        return False
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
    except requests.RequestException:
        return False
    return not is_placeholder_image_bytes(response.content)


def _photo_filename_stamp(url: str) -> str:
    name = url.rsplit("/", 1)[-1]
    match = re.search(r"s(\d{14})", name)
    return match.group(1) if match else ""


def _pick_best_image_url(urls: list[str], target_date: str) -> str:
    if not urls:
        return ""
    dated = [url for url in urls if _photo_filename_stamp(url).startswith(target_date)]
    pool = dated or urls
    return max(pool, key=lambda url: _photo_filename_stamp(url) or "0")


def merge_live_images(cards: list[dict], live_menus: list[dict]) -> list[dict]:
    target_date = str(cards[0].get("date") or "") if cards else ""
    by_key = {
        _menu_key(menu): str(menu.get("imageUrl") or "")
        for menu in live_menus
        if menu.get("imageUrl")
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
    by_course = {
        course: _pick_best_image_url(urls, target_date)
        for course, urls in course_urls.items()
    }

    merged: list[dict] = []
    for card in cards:
        key_url = by_key.get(_menu_key(card), "")
        course_url = by_course.get(card.get("course_type", ""), "")
        candidates = [url for url in (key_url, course_url) if url]
        live_url = _pick_best_image_url(candidates, target_date) if candidates else ""
        if live_url and live_url != card.get("image_url"):
            merged.append({**card, "image_url": live_url})
        else:
            merged.append(card)
    return merged


def drop_placeholder_images(cards: list[dict]) -> list[dict]:
    cleaned: list[dict] = []
    for card in cards:
        url = card.get("image_url") or ""
        if url and not is_real_menu_image(url):
            cleaned.append({**card, "image_url": ""})
        else:
            cleaned.append(card)
    return cleaned


def fetch_live_menus(restaurant_id: str, date: datetime) -> list[dict]:
    try:
        response = requests.get(
            f"{WELPLAN_BASE}/api/menu/live",
            params={
                "kind": "gallery",
                "date": date.strftime("%Y%m%d"),
                "time": "all",
                "restaurantId": restaurant_id,
            },
            headers={"Accept": "application/json", "Cache-Control": "no-store"},
            timeout=LIVE_TIMEOUT,
        )
        if not response.ok:
            return []
        payload = response.json()
    except (requests.RequestException, ValueError):
        return []
    menus = payload.get("menus") if isinstance(payload, dict) else None
    return menus if isinstance(menus, list) else []


def search_restaurants(query: str) -> list[dict]:
    response = requests.get(
        f"{WELPLAN_BASE}/proxy/search",
        params={"q": query},
        timeout=20,
    )
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, list):
        raise RuntimeError("Welplan 검색 응답이 배열이 아닙니다.")
    return data


def restaurant_menu_url(restaurant_id: str, slug: str, date: datetime, vendor: str = DEFAULT_VENDOR) -> str:
    encoded_slug = quote(slug, safe="")
    day = date.strftime("%Y%m%d")
    return f"{WELPLAN_BASE}/restaurants/{vendor}/{restaurant_id}/{encoded_slug}/{day}"


def fetch_menu_html(url: str) -> str:
    response = requests.get(url, headers={"Accept": "text/html"}, timeout=30)
    response.raise_for_status()
    response.encoding = "utf-8"
    return response.text


def parse_lunch_cards(html_text: str, restaurant_id: str = DEFAULT_RESTAURANT_ID) -> list[dict]:
    cards: list[dict] = []
    seen: set[str] = set()
    for match in OBJECT_RE.finditer(html_text):
        if restaurant_id not in match.group("id"):
            continue
        body = match.group("body")
        fields = dict(FIELD_RE.findall(body))
        if fields.get("mealTimeId") != LUNCH_MEAL_TIME_ID:
            continue
        if fields.get("hallNo") != MAIN_HALL:
            continue
        course = fields.get("courseType", "")
        if course not in COURSE_STATIONS or course in seen:
            continue
        calories_matches = [int(value) for value in CALORIES_RE.findall(body)]
        cards.append(
            {
                "menu_id": match.group("id"),
                "name": html.unescape(fields.get("name", "")),
                "course_type": course,
                "station": COURSE_STATIONS[course],
                "image_url": fields.get("imageUrl", ""),
                "calories": calories_matches[-1] if calories_matches else 0,
                "hall_no": fields.get("hallNo", ""),
                "vendor": fields.get("vendor", DEFAULT_VENDOR),
                "restaurant_id": restaurant_id,
                "date": fields.get("date", ""),
                "meal_time_id": fields.get("mealTimeId", ""),
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
    response = requests.get(
        f"{WELPLAN_BASE}/proxy/{restaurant_id}/menus/detail",
        params={
            "date": date.strftime("%Y%m%d"),
            "mealTimeId": LUNCH_MEAL_TIME_ID,
            "hallNo": hall_no,
            "courseType": course_type,
            "nutrient": "1",
        },
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list):
        return []
    rows: list[dict] = []
    for row in payload:
        name = html.unescape(str(row.get("name") or "")).strip()
        if not name:
            continue
        nutrition = row.get("nutrition") or {}
        calories = int(nutrition.get("calories") or 0)
        rows.append({"name": name, "calories": calories})
    return rows


def _kcal_text(calories: int) -> str:
    if calories <= 0:
        return ""
    return f"{calories:,}kcal"


def cards_to_day_menu(cards: list[dict], details: dict[str, list[dict]], date_label: str) -> DayMenu:
    by_course = {card["course_type"]: card for card in cards}
    mains: list[StationMenu] = []
    extra: StationMenu | None = None
    ramen: StationMenu | None = None
    for course in (*MAIN_ORDER, *SECOND_ORDER):
        card = by_course.get(course)
        if not card:
            continue
        rows = details.get(course) or [{"name": card["name"], "calories": card["calories"]}]
        names = [row["name"] for row in rows]
        calories = card["calories"]
        if course == "DD" and not calories:
            calories = sum(row["calories"] for row in rows)
        menu = StationMenu(
            station=card["station"],
            name=names[0],
            kcal=_kcal_text(calories),
            items=names[1:],
            image_url=card["image_url"],
            course_type=course,
        )
        if course in MAIN_ORDER:
            mains.append(menu)
        elif course == "DD":
            ramen = menu
        else:
            extra = menu
    return DayMenu(date_label=date_label, mains=mains, extra=extra, ramen=ramen)


def _ensure_ramen_card(cards: list[dict], restaurant_id: str, date: datetime) -> list[dict]:
    if any(card["course_type"] == "DD" for card in cards):
        return cards
    rows = fetch_course_detail(restaurant_id, date, MAIN_HALL, "DD")
    if not rows:
        return cards
    cards.append(
        {
            "menu_id": f"{date.strftime('%Y%m%d')}-{restaurant_id}-{MAIN_HALL}-DD",
            "name": rows[0]["name"],
            "course_type": "DD",
            "station": COURSE_STATIONS["DD"],
            "image_url": "",
            "calories": sum(row["calories"] for row in rows),
            "hall_no": MAIN_HALL,
            "vendor": DEFAULT_VENDOR,
            "restaurant_id": restaurant_id,
            "date": date.strftime("%Y%m%d"),
            "meal_time_id": LUNCH_MEAL_TIME_ID,
        }
    )
    return cards


def fetch_today_menu_from_welplan(
    restaurant_id: str = DEFAULT_RESTAURANT_ID,
    slug: str = DEFAULT_SLUG,
    timezone: str = "Asia/Seoul",
    meal: str = "점심",
) -> DayMenu:
    del meal
    today = now_in(timezone)
    url = restaurant_menu_url(restaurant_id, slug, today)
    page = fetch_menu_html(url)
    cards = parse_lunch_cards(page, restaurant_id)
    cards = _ensure_ramen_card(cards, restaurant_id, today)
    live_menus = fetch_live_menus(restaurant_id, today)
    if live_menus:
        cards = merge_live_images(cards, live_menus)
    details: dict[str, list[dict]] = {}
    for card in cards:
        details[card["course_type"]] = fetch_course_detail(
            restaurant_id,
            today,
            card["hall_no"],
            card["course_type"],
        )
    menu = cards_to_day_menu(cards, details, today.strftime("%Y-%m-%d"))
    menu.raw_text = page
    return menu
