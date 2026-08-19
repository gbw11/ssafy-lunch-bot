from lunchbot.models import DayMenu, StationMenu
from lunchbot.welstory import meal_photo_url, meal_photos

RECIPE_DIR = "https://img-welmenu.welstory.com/data/manager/recipe/E32M/20260819/"


def test_meal_photo_url_joins_photo_fields() -> None:
    assert (
        meal_photo_url({"photoUrl": RECIPE_DIR, "photoCd": "s20260819112421.jpg"})
        == f"{RECIPE_DIR}s20260819112421.jpg"
    )
    assert meal_photo_url({"photoUrl": "", "photoCd": "x.jpg"}) == ""
    assert meal_photo_url({"photoUrl": "ftp://nope/", "photoCd": "x.jpg"}) == ""


def test_meal_photos_keyed_by_course_and_station() -> None:
    photos = meal_photos(
        [
            {
                "menuCourseType": "A1",
                "courseTxt": "1코너: 브라운그릴",
                "photoUrl": RECIPE_DIR,
                "photoCd": "a.jpg",
            },
            {"menuCourseType": "AA", "courseTxt": "동방식객", "photoUrl": "", "photoCd": "b.jpg"},
        ]
    )
    assert photos == {"A1": f"{RECIPE_DIR}a.jpg", "브라운그릴": f"{RECIPE_DIR}a.jpg"}


def test_fill_photos_overrides_recipe_placeholder() -> None:
    menu = DayMenu(
        date_label="2026-08-19",
        mains=[
            StationMenu(
                station="브라운그릴",
                name="소불고기",
                image_url="https://img-welmenu.welstory.com/placeholder.jpg",
                course_type="A1",
            )
        ],
    )
    meals = [
        {
            "menuCourseType": "A1",
            "courseTxt": "브라운그릴",
            "photoUrl": "https://img-welmenu.welstory.com/live/",
            "photoCd": "today.jpg",
        }
    ]
    menu.fill_photos(meal_photos(meals), needs_photo=lambda item: True)

    assert menu.mains[0].image_url == "https://img-welmenu.welstory.com/live/today.jpg"
