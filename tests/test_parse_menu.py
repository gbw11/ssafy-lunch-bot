from pathlib import Path

from lunchbot.format_message import format_mattermost_message
from lunchbot.parse_menu import parse_menu_text

SAMPLE = Path(__file__).parent / "fixtures" / "sample_page.txt"


def test_parse_sample_menu() -> None:
    menu = parse_menu_text(SAMPLE.read_text(encoding="utf-8"), date_label="2026-08-19")

    assert menu.has_content
    assert [item.station for item in menu.mains] == ["브라운그릴", "동방식객", "모던키친", "별미공방"]
    assert menu.mains[0].name == "[테이스티가든] 소불고기"
    assert "1263kcal" in menu.mains[0].kcal.replace(",", "")
    assert menu.mains[1].rating.startswith("4.3")
    assert menu.extra is not None
    assert "오징어주꾸미숙회" in menu.extra.name
    assert menu.ramen is not None
    assert menu.ramen.station == "마이보글"
    assert "신라면" in menu.ramen.items


def test_format_message_contains_key_sections() -> None:
    menu = parse_menu_text(SAMPLE.read_text(encoding="utf-8"), date_label="2026-08-19")
    text = format_mattermost_message(menu)

    assert "오늘의 점심 메뉴" in text or menu.has_content
