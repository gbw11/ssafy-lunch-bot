from lunchbot.message import IMAGE_HEIGHT, IMAGE_WIDTH, format_message
from lunchbot.models import DayMenu, StationMenu

SIZE = f"={IMAGE_WIDTH}x{IMAGE_HEIGHT}"


def _menu() -> DayMenu:
    return DayMenu(
        date_label="2026-08-19",
        mains=[
            StationMenu(
                station="브라운그릴",
                name="소불고기",
                kcal="1,263kcal",
                items=["브로컬리"],
                image_url="https://img-welmenu.welstory.com/a.jpg",
                course_type="A1",
            ),
            StationMenu(station="동방식객", name="물냉면", course_type="AA"),
        ],
        ramen=StationMenu(
            station="마이보글",
            name="라면 14종 중 택1",
            image_url="https://img-welmenu.welstory.com/e.jpg",
            course_type="DD",
        ),
        extra=StationMenu(station="추가배식대", name="숙회", course_type="HH"),
    )


def test_every_photo_gets_the_same_size() -> None:
    text = format_message(_menu())
    assert f"![](https://img-welmenu.welstory.com/a.jpg {SIZE})" in text
    assert f"![](https://img-welmenu.welstory.com/e.jpg {SIZE})" in text
    assert text.count(SIZE) == text.count("![](")


def test_missing_photo_leaves_cell_empty() -> None:
    text = format_message(_menu())
    assert text.count("![](") == 2  # 사진 있는 코너만


def test_tables_split_mains_and_extras() -> None:
    text = format_message(_menu())
    assert text.startswith("### :yum: 오늘의 점심 메뉴 :whatistodaylunch:")
    assert "| **브라운그릴** | **동방식객** |" in text
    assert "| **마이보글** | **추가배식대** |" in text
    assert "소불고기,브로컬리 (1,263kcal)" in text


def test_empty_menu_is_heading_only() -> None:
    menu = DayMenu(date_label="2026-08-19")
    assert not menu.has_content
    assert format_message(menu) == "### :yum: 오늘의 점심 메뉴 :whatistodaylunch:"
