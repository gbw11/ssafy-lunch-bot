"""welstory-meal.cloud 사진 폴백 테스트."""

from __future__ import annotations

from lunchbot.mealcloud import DEFAULT_URL, meal_photos, meals_url
from lunchbot.models import DayMenu, StationMenu

# 2026-09-01 실제 응답을 줄인 것. 이 사이트는 3·4번 코너를 '한식사계'/'모던키친' 으로
# 부르는데 welplan 은 같은 메뉴를 '모던키친'/'별미공방' 이라고 부릅니다.
PAYLOAD = {
    "date": "2026-09-01",
    "status": "READY",
    "meals": [
        {
            "id": "meal-01",
            "courseName": "브라운그릴",
            "name": "허니머스터드고구마피자&갈릭소스",
            "description": "허니머스터드고구마피자&갈릭소스,타코샐러드,오이피클,탄산음료",
            "imageUrl": "/api/meals/2026-09-01/images/meal-01?v=aaa",
        },
        {
            "id": "meal-03",
            "courseName": "한식사계",
            "name": "크림파스탕",
            "description": "크림파스탕,브라운브레드1/2&초코소스,타코샐러드,무비트피클",
            "imageUrl": "/api/meals/2026-09-01/images/meal-03?v=bbb",
        },
        {
            "id": "meal-04",
            "courseName": "모던키친",
            "name": "돼지국밥&소면사리",
            "description": "돼지국밥&소면사리,흰쌀밥,죽봉어묵조림",
            "imageUrl": "",  # 아직 실사진이 안 올라온 코너.
        },
    ],
}


def test_meals_url() -> None:
    assert meals_url() == f"{DEFAULT_URL}/api/meals"
    assert meals_url("https://example.com/") == "https://example.com/api/meals"


def test_meal_photos_keys_by_menu_name_and_absolutizes_urls() -> None:
    photos = meal_photos(PAYLOAD)

    assert photos["허니머스터드고구마피자갈릭소스"] == (
        f"{DEFAULT_URL}/api/meals/2026-09-01/images/meal-01?v=aaa"
    )
    assert photos["크림파스탕"].endswith("meal-03?v=bbb")
    # 사진 없는 코너와 사이트 코너명은 키로 쓰지 않습니다(코너명이 어긋나는 날이 있음).
    assert not any("돼지국밥" in key for key in photos)
    assert "모던키친" not in photos


def test_fill_photos_matches_by_menu_name_even_when_station_names_differ() -> None:
    menu = DayMenu(
        date_label="2026-09-01",
        mains=[
            StationMenu(
                station="모던키친",
                name="크림파스탕",
                items=["브라운브레드1/2&초코소스"],
                course_type="BB",
            ),
            StationMenu(station="별미공방", name="돼지국밥&소면사리", course_type="CC"),
        ],
    )
    menu.fill_photos(meal_photos(PAYLOAD), needs_photo=lambda item: not item.image_url)

    assert menu.mains[0].image_url.endswith("meal-03?v=bbb")
    assert menu.mains[1].image_url == ""  # 사진이 없으면 그대로 빈칸.


def test_fill_photos_only_fills_missing() -> None:
    menu = DayMenu(
        date_label="2026-09-01",
        mains=[
            StationMenu(station="브라운그릴", name="크림파스탕", image_url=""),
            StationMenu(station="동방식객", name="크림파스탕", image_url="https://keep.example/x.jpg"),
        ],
    )
    menu.fill_photos(meal_photos(PAYLOAD), needs_photo=lambda item: not item.image_url)

    assert menu.mains[0].image_url.endswith("meal-03?v=bbb")
    assert menu.mains[1].image_url == "https://keep.example/x.jpg"


def test_meal_photos_drops_ambiguous_keys() -> None:
    payload = {
        "meals": [
            {"name": "흰쌀밥", "description": "흰쌀밥,국", "imageUrl": "/a.jpg"},
            {"name": "흰쌀밥", "description": "흰쌀밥,김치", "imageUrl": "/b.jpg"},
        ]
    }
    assert "흰쌀밥" not in meal_photos(payload)
