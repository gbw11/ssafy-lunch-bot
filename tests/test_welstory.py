from lunchbot.parse_menu import DayMenu, StationMenu
from lunchbot.welstory import apply_meal_photos, meal_photo_url, meals_to_day_menu


def test_meals_to_day_menu() -> None:
    meals = [
        {
            "courseTxt": "브라운그릴",
            "menuName": "소불고기",
            "sumKcal": "1263",
            "subMenuTxt": "소불고기, 브로컬리, 라이스",
        },
        {
            "courseTxt": "추가 배식대",
            "menuName": "오징어주꾸미숙회",
            "sumKcal": "",
            "subMenuTxt": "그린샐러드 / 포기김치",
        },
        {
            "courseTxt": "마이보글",
            "menuName": "라면 14종 중 택1",
            "sumKcal": "",
            "subMenuTxt": "신라면, 진라면",
        },
    ]
    menu = meals_to_day_menu(meals, "2026-08-19")
    assert menu.mains[0].station == "브라운그릴"
    assert menu.mains[0].kcal == "1263kcal"
    assert menu.extra is not None and "김치" in "".join(menu.extra.items)
    assert menu.ramen is not None and menu.ramen.station == "마이보글"


def test_meal_photo_url_joins_photo_fields() -> None:
    assert (
        meal_photo_url(
            {
                "photoUrl": "https://img-welmenu.welstory.com/data/manager/recipe/E32M/20260819/",
                "photoCd": "s20260819112421.jpg",
            }
        )
        == "https://img-welmenu.welstory.com/data/manager/recipe/E32M/20260819/s20260819112421.jpg"
    )
    assert meal_photo_url({"photoUrl": "", "photoCd": "x.jpg"}) == ""


def test_apply_meal_photos_overrides_recipe_placeholder() -> None:
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
    apply_meal_photos(
        menu,
        [
            {
                "menuCourseType": "A1",
                "courseTxt": "브라운그릴",
                "photoUrl": "https://img-welmenu.welstory.com/live/",
                "photoCd": "today.jpg",
            }
        ],
    )
    assert menu.mains[0].image_url == "https://img-welmenu.welstory.com/live/today.jpg"
