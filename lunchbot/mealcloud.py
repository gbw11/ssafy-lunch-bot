"""welstory-meal.cloud — 코너 사진 폴백.

BOB SSAFY(Streamlit)를 대신합니다. 브라우저 없이 JSON API 한 번만 부르면 되고,
사이트가 "메뉴 이미지 준비 중" 화면을 감지해 실사진이 올라올 때까지 기다려 주므로
사진이 아직 없는 날은 `status: WAITING` 과 빈 imageUrl 로 내려옵니다.
"""

from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urljoin

import requests

from lunchbot.models import DEFAULT_TIMEZONE, DayMenu, PhotoSet, StationMenu, menu_key, now_in

DEFAULT_URL = "https://welstory-meal.cloud"
TIMEOUT = 30
HEADERS = {"Accept": "application/json"}
CALORIE_DIGITS_RE = re.compile(r"[\d,]+")
# 대표 메뉴명 없이 넘어오는 코너는 걸러야 하는 다른 방식의 마이보글/추가배식대 이름.
RAMEN_STATION = "마이보글"
EXTRA_STATION = "추가배식대"


class MealCloudError(RuntimeError):
    pass


def meals_url(base_url: str = DEFAULT_URL) -> str:
    return urljoin(base_url.rstrip("/") + "/", "api/meals")


def _image_url(image: str, base_url: str) -> str:
    if image.startswith("http"):
        return image
    return urljoin(base_url.rstrip("/") + "/", image.lstrip("/"))


def _meals(payload: dict) -> list[dict]:
    meals = payload.get("meals") if isinstance(payload, dict) else None
    if not isinstance(meals, list):
        raise MealCloudError("welstory-meal.cloud 응답에 meals 목록이 없습니다.")
    return [meal for meal in meals if isinstance(meal, dict)]


def meal_photos(payload: dict, base_url: str = DEFAULT_URL) -> dict[str, str]:
    """메뉴명 키 → 사진 URL.

    이 사이트가 붙이는 코너명(courseName)은 welplan 코너명과 어긋나는 날이 있고
    (예: 2026-09-01 은 3·4번 코너를 '한식사계'/'모던키친' 으로 부르고,
    welplan 은 '모던키친'/'별미공방' 으로 부릅니다) 코너 순서도 날마다 달라서,
    코너명이나 순서가 아니라 **메뉴명**으로 짝지웁니다.
    """
    meals = _meals(payload)
    photos: dict[str, str] = {}
    ambiguous: set[str] = set()
    for meal in meals:
        image = str(meal.get("imageUrl") or "").strip()
        if not image:
            continue  # 아직 실사진이 안 올라온 코너.
        url = _image_url(image, base_url)
        description = str(meal.get("description") or "")
        candidates = (meal.get("name"), description, description.split(",")[0])
        for key in (menu_key(value) for value in candidates):
            if not key or key in ambiguous:
                continue
            if key in photos and photos[key] != url:
                # 두 코너가 같은 키를 주면(반찬 이름 겹침 등) 잘못 붙는 걸 막습니다.
                del photos[key]
                ambiguous.add(key)
                continue
            photos[key] = url
    return photos


def meal_dishes(payload: dict, base_url: str = DEFAULT_URL) -> dict[str, frozenset[str]]:
    """사진 URL → 그 사진에 딸린 메뉴·반찬 이름 키들.

    대표 메뉴명이 welplan 과 어긋나는 날(예: `돈육순두부찌개` 를 `돈육두부찌개` 로
    적는 날) 반찬 구성으로 코너를 찾아내기 위한 재료입니다.
    """
    dishes: dict[str, frozenset[str]] = {}
    for meal in _meals(payload):
        image = str(meal.get("imageUrl") or "").strip()
        if not image:
            continue
        names = [meal.get("name"), *str(meal.get("description") or "").split(",")]
        keys = frozenset(key for key in (menu_key(name) for name in names) if key)
        if not keys:
            continue
        url = _image_url(image, base_url)
        dishes[url] = dishes.get(url, frozenset()) | keys
    return dishes


def meal_photo_set(payload: dict, base_url: str = DEFAULT_URL) -> PhotoSet:
    return PhotoSet(
        by_key=meal_photos(payload, base_url),
        dishes=meal_dishes(payload, base_url),
    )


def _calories(text: str) -> int:
    match = CALORIE_DIGITS_RE.search(text or "")
    return int(match.group().replace(",", "")) if match else 0


def _station_menu(meal: dict, base_url: str) -> StationMenu:
    """코너 하나를 `StationMenu`로. 대표 메뉴명은 description 첫 항목과 같아 뺍니다."""
    items = [part.strip() for part in str(meal.get("description") or "").split(",")]
    image = str(meal.get("imageUrl") or "").strip()
    calories = _calories(str(meal.get("calorie") or ""))
    return StationMenu(
        station=str(meal.get("courseName") or "").strip(),
        name=str(meal.get("name") or "").strip(),
        kcal=f"{calories:,}kcal" if calories else "",
        items=[item for item in items[1:] if item],
        image_url=_image_url(image, base_url) if image else "",
    )


def day_menu(payload: dict, date_label: str, base_url: str = DEFAULT_URL) -> DayMenu:
    """Welplan이 죽었을 때 메뉴 텍스트+사진을 통째로 이 소스에서 만듭니다.

    이 사이트가 부르는 코너명이 welplan과 어긋나는 날이 있으므로(모듈 상단 설명
    참고) 표에는 이 소스가 부르는 코너 이름 그대로 찍힙니다.
    """
    menu = DayMenu(date_label=date_label)
    for meal in _meals(payload):
        station = _station_menu(meal, base_url)
        if not station.name:
            continue
        if station.station == RAMEN_STATION:
            menu.ramen = station
        elif station.station == EXTRA_STATION:
            menu.extra = station
        else:
            menu.mains.append(station)
    return menu


def fetch_today_menu(
    base_url: str = DEFAULT_URL,
    timezone: str = DEFAULT_TIMEZONE,
    date: datetime | None = None,
) -> DayMenu:
    day = date or now_in(timezone)
    payload = _fetch_meals_payload(base_url, day)
    return day_menu(payload, f"{day:%Y-%m-%d}", base_url)


def _fetch_meals_payload(base_url: str, day: datetime) -> dict:
    try:
        response = requests.get(
            meals_url(base_url),
            params={"date": f"{day:%Y-%m-%d}"},
            headers=HEADERS,
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        raise MealCloudError(f"welstory-meal.cloud 연결 실패: {exc}") from exc
    except ValueError as exc:
        raise MealCloudError("welstory-meal.cloud 응답이 JSON이 아닙니다.") from exc


def fetch_photos(
    base_url: str = DEFAULT_URL,
    timezone: str = DEFAULT_TIMEZONE,
    date: datetime | None = None,
) -> PhotoSet:
    day = date or now_in(timezone)
    payload = _fetch_meals_payload(base_url, day)
    return meal_photo_set(payload, base_url)
