"""welstory-meal.cloud 사진 폴백 테스트."""

from __future__ import annotations

from lunchbot.mealcloud import DEFAULT_URL, meal_photo_set, meal_photos, meals_url
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


# 2026-09-04 실제 응답을 줄인 것. mealcloud 는 3번 코너 대표명을 `돈육두부찌개` 로
# 적지만 welplan 은 `돈육순두부찌개` 라고 적어서, 대표명 정확 일치로는 못 붙습니다.
VOTE_PAYLOAD = {
    "date": "2026-09-04",
    "meals": [
        {
            "courseName": "모던사계",
            "name": "돈육두부찌개",
            "description": "돈육두부찌개,흰쌀밥,생깻잎전&간장,다시마채젓갈무침,오이생채",
            "imageUrl": "/api/meals/2026-09-04/images/meal-03?v=ccc",
        },
        {
            "courseName": "한식사계",
            "name": "가자미채소영양밥",
            "description": "가자미채소영양밥,청양초시락국,생깻잎전&간장,탕평채",
            "imageUrl": "/api/meals/2026-09-04/images/meal-04?v=ddd",
        },
    ],
}


def _modern_kitchen() -> StationMenu:
    return StationMenu(
        station="모던키친",
        course_type="BB",
        name="돈육순두부찌개",
        items=["흰쌀밥", "생깻잎전&간장", "다시마채젓갈무침", "돌나물유자청무침"],
    )


def _byeolmi() -> StationMenu:
    return StationMenu(
        station="별미공방",
        course_type="CC",
        name="가자미채소영양밥",
        items=["청양초시락국", "생깻잎전&간장", "탕평채"],
    )


def test_dish_votes_match_corner_when_main_name_differs() -> None:
    """2026-09-04 재현: 대표명이 한 글자 달라도 반찬 겹침으로 사진을 붙여야 합니다."""
    menu = DayMenu(date_label="2026-09-04", mains=[_modern_kitchen(), _byeolmi()])
    menu.fill_photos(meal_photo_set(VOTE_PAYLOAD), needs_photo=lambda item: not item.image_url)
    assert menu.mains[0].image_url.endswith("meal-03?v=ccc")  # 득표로 붙은 코너
    assert menu.mains[1].image_url.endswith("meal-04?v=ddd")  # 대표명 정확 일치


def test_dish_votes_never_reuse_a_photo_taken_by_exact_match() -> None:
    """별미공방이 정확 일치로 가져간 사진을 모던키친이 다시 쓰면 안 됩니다."""
    menu = DayMenu(date_label="2026-09-04", mains=[_modern_kitchen(), _byeolmi()])
    menu.fill_photos(meal_photo_set(VOTE_PAYLOAD), needs_photo=lambda item: not item.image_url)
    urls = [item.image_url for item in menu.stations]
    assert len(set(urls)) == len(urls)


def test_dish_votes_skip_when_single_shared_dish() -> None:
    """반찬 하나만 겹치는 건 근거가 약해 붙이지 않습니다(틀린 사진 방지)."""
    weak = StationMenu(station="모던키친", course_type="BB", name="전혀다른메뉴", items=["흰쌀밥"])
    menu = DayMenu(date_label="2026-09-04", mains=[weak])
    menu.fill_photos(meal_photo_set(VOTE_PAYLOAD), needs_photo=lambda item: not item.image_url)
    assert menu.mains[0].image_url == ""


def test_dish_votes_skip_on_tie() -> None:
    """두 사진이 동점이면 어느 쪽인지 알 수 없어 비워 둡니다."""
    payload = {
        "meals": [
            {"name": "A", "description": "A,흰쌀밥,탕평채", "imageUrl": "/img/a?v=1"},
            {"name": "B", "description": "B,흰쌀밥,탕평채", "imageUrl": "/img/b?v=2"},
        ]
    }
    item = StationMenu(station="모던키친", course_type="BB", name="C", items=["흰쌀밥", "탕평채"])
    menu = DayMenu(date_label="2026-09-04", mains=[item])
    menu.fill_photos(meal_photo_set(payload), needs_photo=lambda i: not i.image_url)
    assert menu.mains[0].image_url == ""
