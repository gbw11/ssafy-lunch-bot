"""welstory-meal.cloud — 코너 사진 폴백.

BOB SSAFY(Streamlit)를 대신합니다. 브라우저 없이 JSON API 한 번만 부르면 되고,
사이트가 "메뉴 이미지 준비 중" 화면을 감지해 실사진이 올라올 때까지 기다려 주므로
사진이 아직 없는 날은 `status: WAITING` 과 빈 imageUrl 로 내려옵니다.
"""

from __future__ import annotations

from datetime import datetime
from urllib.parse import urljoin

import requests

from lunchbot.models import DEFAULT_TIMEZONE, menu_key, now_in

DEFAULT_URL = "https://welstory-meal.cloud"
TIMEOUT = 30
HEADERS = {"Accept": "application/json"}


class MealCloudError(RuntimeError):
    pass


def meals_url(base_url: str = DEFAULT_URL) -> str:
    return urljoin(base_url.rstrip("/") + "/", "api/meals")


def meal_photos(payload: dict, base_url: str = DEFAULT_URL) -> dict[str, str]:
    """메뉴명 키 → 사진 URL.

    이 사이트가 붙이는 코너명(courseName)은 welplan 코너명과 어긋나는 날이 있고
    (예: 2026-09-01 은 3·4번 코너를 '한식사계'/'모던키친' 으로 부르고,
    welplan 은 '모던키친'/'별미공방' 으로 부릅니다) 코너 순서도 날마다 달라서,
    코너명이나 순서가 아니라 **메뉴명**으로 짝지웁니다.
    """
    meals = payload.get("meals") if isinstance(payload, dict) else None
    if not isinstance(meals, list):
        raise MealCloudError("welstory-meal.cloud 응답에 meals 목록이 없습니다.")

    photos: dict[str, str] = {}
    ambiguous: set[str] = set()
    for meal in meals:
        if not isinstance(meal, dict):
            continue
        image = str(meal.get("imageUrl") or "").strip()
        if not image:
            continue  # 아직 실사진이 안 올라온 코너.
        url = image if image.startswith("http") else urljoin(base_url.rstrip("/") + "/", image.lstrip("/"))
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


def fetch_photos(
    base_url: str = DEFAULT_URL,
    timezone: str = DEFAULT_TIMEZONE,
    date: datetime | None = None,
) -> dict[str, str]:
    day = date or now_in(timezone)
    try:
        response = requests.get(
            meals_url(base_url),
            params={"date": f"{day:%Y-%m-%d}"},
            headers=HEADERS,
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        raise MealCloudError(f"welstory-meal.cloud 연결 실패: {exc}") from exc
    except ValueError as exc:
        raise MealCloudError("welstory-meal.cloud 응답이 JSON이 아닙니다.") from exc
    return meal_photos(payload, base_url)
