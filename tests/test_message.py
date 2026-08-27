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
    # 메뉴는 표 안, 사진 칸 바로 아래에 한 줄씩. 콤마로 몰아넣으면 열이 넓어져 사진이 눌립니다.
    assert "| 소불고기 | 물냉면 |" in text
    assert "| 브로컬리 |  |" in text
    assert "| **1,263kcal** |  |" in text
    assert "소불고기,브로컬리" not in text


def test_empty_menu_is_heading_only() -> None:
    menu = DayMenu(date_label="2026-08-19")
    assert not menu.has_content
    assert format_message(menu) == "### :yum: 오늘의 점심 메뉴 :whatistodaylunch:"


def test_drops_only_the_photo_row_when_no_photos() -> None:
    """사진이 없는 날엔 사진 행만 빠지고, 메뉴 표는 그대로 나와야 합니다."""
    menu = DayMenu(
        date_label="2026-08-26",
        mains=[
            StationMenu(station="브라운그릴", name="불고기", kcal="923kcal", course_type="A1"),
            StationMenu(station="동방식객", name="파스타", kcal="889kcal", course_type="AA"),
        ],
    )
    text = format_message(menu)
    assert "![](" not in text  # 빈 칸만 남을 사진 행은 빼고
    assert "| **브라운그릴** | **동방식객** |" in text  # 표 자체는 유지
    assert "| 불고기 | 파스타 |" in text
    assert "| **923kcal** | **889kcal** |" in text


def test_every_row_has_the_same_cell_count() -> None:
    """열이 밀리면 표가 깨지므로, 항목 수가 다른 코너는 빈 칸으로 채워야 합니다."""
    text = format_message(_menu())
    for block in text.split("\n\n")[1:]:
        widths = {line.count("|") for line in block.splitlines()}
        assert len(widths) == 1, block


def test_no_cell_is_wider_than_the_photo() -> None:
    """어떤 셀도 사진(240px)보다 넓어지면 그 열만 늘어나 다른 사진이 작게 렌더됩니다."""
    text = format_message(_menu())
    for line in text.splitlines():
        if not line.startswith("|") or "![](" in line or ":---:" in line:
            continue
        for cell in line.strip("|").split("|"):
            # 한글 기준 대략 14px/자 → 240px 안에 들어오는 길이인지만 봅니다.
            assert len(cell.strip().replace("*", "")) <= 17, cell


def test_bracket_label_goes_on_its_own_line() -> None:
    """분류 라벨까지 붙이면 그 열만 사진보다 넓어져 다른 사진이 작아집니다."""
    menu = DayMenu(
        date_label="2026-08-27",
        mains=[
            StationMenu(
                station="별미공방",
                name="[임직원인기메뉴] 반반불고기덮밥",
                kcal="902kcal",
                items=["온육수"],
                image_url="https://img-welmenu.welstory.com/d.jpg",
                course_type="CC",
            ),
        ],
    )
    text = format_message(menu)
    assert "| [임직원인기메뉴] |" in text
    assert "| 반반불고기덮밥 |" in text
    assert "[임직원인기메뉴] 반반불고기덮밥" not in text


def test_label_only_name_is_not_split() -> None:
    """'[라면 14종 중 택1]' 처럼 라벨만 있는 이름은 쪼갤 게 없습니다."""
    menu = DayMenu(
        date_label="2026-08-27",
        ramen=StationMenu(station="마이보글", name="[라면 14종 중 택1]", course_type="DD"),
    )
    assert "| [라면 14종 중 택1] |" in format_message(menu)
