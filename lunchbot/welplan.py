"""Welplan(welplan.pmh.codes) — 메뉴 원본과 당일 사진 1차 소스."""

from __future__ import annotations

import hashlib
import html
import re
import time
from concurrent.futures import ThreadPoolExecutor
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
# Welplan은 가끔 몇십 초씩 502/503을 낸다. 하루 한 번뿐인 실행이 단발 장애로
# 통째로 날아가지 않게 여기서만 재시도한다.
RETRY_STATUSES = frozenset({502, 503, 504})
RETRY_BACKOFF_SECONDS = (5, 15, 30)

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
        # 판정 불가일 뿐 사진이 없는 건 아닙니다. CI 러너에서 이미지 CDN 접근이
        # 실패하는 일이 있어, 여기서 False를 주면 멀쩡한 사진까지 지워집니다.
        return True
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


def _meal_time_id(item: dict) -> str:
    """live API 응답과 카드에서 끼니 구분(1 조식 / 2 중식 / 3 석식)을 읽습니다."""
    return str(item.get("mealTimeId") or item.get("meal_time_id") or "")


def _is_lunch(item: dict) -> bool:
    """끼니 표기가 없으면(필드 누락) 버리지 않고 살립니다."""
    meal_time = _meal_time_id(item)
    return meal_time in {LUNCH_MEAL_TIME_ID, ""}


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


def course_photos(live_menus: list[dict], target_date: str) -> dict[str, str]:
    """본관 점심 사진만 코너코드별로 모읍니다."""
    course_urls: dict[str, list[str]] = {}
    for menu in live_menus:
        if menu.get("hallNo") not in {MAIN_HALL, None, ""}:
            continue
        if target_date and str(menu.get("date") or "") != target_date:
            continue
        # 조식/석식 사진은 같은 코너코드를 쓰면서 새벽에 먼저 올라옵니다.
        # 끼니를 안 거르면 점심 사진 대신 그날 조식 사진이 실립니다.
        if not _is_lunch(menu):
            continue
        course = str(menu.get("courseType") or "")
        url = str(menu.get("imageUrl") or "")
        if course and url:
            course_urls.setdefault(course, []).append(url)
    return {course: _best_photo(urls, target_date) for course, urls in course_urls.items()}


def fetch_live_photos(restaurant_id: str, date: datetime) -> dict[str, str]:
    """코너코드 → 당일 점심 사진 URL. 사진이 올라오길 기다리며 다시 부를 때 씁니다."""
    day = f"{date:%Y%m%d}"
    return course_photos(fetch_live_menus(restaurant_id, date), day)


def merge_live_images(cards: list[dict], live_menus: list[dict]) -> list[dict]:
    """live API 사진(당일 실사진)으로 카드의 레시피 사진을 갈아끼웁니다."""
    target_date = str(cards[0].get("date") or "") if cards else ""
    by_key = {
        _menu_key(menu): str(menu["imageUrl"])
        for menu in live_menus
        if menu.get("imageUrl") and _is_lunch(menu)
    }
    by_course = course_photos(live_menus, target_date)

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
        # 코너 상세(반찬 목록)는 있으면 좋은 정보일 뿐입니다. 상위 프록시가 죽으면
        # (예: nutrient 캐시 미스로 500) 여기서 예외를 올려 급식표 전체가 안 나갑니다.
        # 상세가 없으면 카드에 있는 대표 메뉴명/열량만으로 보냅니다.
        required=False,
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


def _ramen_card(restaurant_id: str, date: datetime, rows: list[dict]) -> dict:
    """마이보글(DD)은 카드로 안 나오는 날이 있어 상세 응답으로 직접 만듭니다."""
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


def _get_menu_page(url: str) -> requests.Response:
    """메뉴 원본 HTML을 받는다. 일시적 5xx·타임아웃은 백오프하며 다시 시도한다."""
    last_error: Exception | None = None
    for wait in (*RETRY_BACKOFF_SECONDS, None):
        try:
            response = requests.get(url, headers={"Accept": "text/html"}, timeout=30)
            if response.status_code not in RETRY_STATUSES:
                response.raise_for_status()
                return response
            last_error = requests.HTTPError(
                f"{response.status_code} {response.reason} for url: {url}", response=response
            )
        except requests.RequestException as exc:
            last_error = exc
        if wait is None:
            break
        print(f"Welplan 응답 실패({last_error}) — {wait}초 후 재시도합니다.")
        time.sleep(wait)
    raise last_error


def fetch_today_menu(
    restaurant_id: str = DEFAULT_RESTAURANT_ID,
    slug: str = DEFAULT_SLUG,
    timezone: str = DEFAULT_TIMEZONE,
) -> DayMenu:
    today = now_in(timezone)
    response = _get_menu_page(restaurant_menu_url(restaurant_id, slug, today))
    response.encoding = "utf-8"

    cards = parse_lunch_cards(response.text, restaurant_id)
    details: dict[str, list[dict]] = {}
    if not any(card["course_type"] == "DD" for card in cards):
        # 여기서 받은 반찬 목록을 details에도 그대로 써서 같은 상세를 두 번 부르지 않습니다.
        rows = fetch_course_detail(restaurant_id, today, MAIN_HALL, "DD")
        if rows:
            cards.append(_ramen_card(restaurant_id, today, rows))
            details["DD"] = rows

    live_menus = fetch_live_menus(restaurant_id, today)
    if live_menus:
        cards = merge_live_images(cards, live_menus)

    # 코너 상세는 서로 독립이라 병렬로 받습니다(최대 6코너 직렬 왕복 → 1 왕복).
    remaining = [card for card in cards if card["course_type"] not in details]
    if remaining:
        with ThreadPoolExecutor(max_workers=len(remaining)) as pool:
            fetched = pool.map(
                lambda card: fetch_course_detail(
                    restaurant_id, today, card["hall_no"], card["course_type"]
                ),
                remaining,
            )
        details.update(zip((card["course_type"] for card in remaining), fetched))
    return cards_to_day_menu(cards, details, f"{today:%Y-%m-%d}")
