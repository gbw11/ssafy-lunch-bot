from __future__ import annotations

from lunchbot.parse_menu import DayMenu, StationMenu
from lunchbot.welplan import MAIN_ORDER, SECOND_ORDER

MAX_SIDES = 3


def _desc(item: StationMenu, max_sides: int | None = MAX_SIDES) -> str:
    sides = item.items if max_sides is None else item.items[:max_sides]
    names = [item.name, *sides]
    text = ",".join(name.strip() for name in names if name.strip())
    if item.kcal:
        kcal = item.kcal.replace("kcal", "")
        text = f"{text} ({kcal}kcal)" if text else f"({kcal}kcal)"
    return text


def _image(item: StationMenu) -> str:
    if not item.image_url:
        return ""
    return f"![]({item.image_url})"


def _table(items: list[StationMenu], max_sides: int | None = MAX_SIDES) -> str:
    if not items:
        return ""
    headers = " | ".join(f"**{item.station}**" for item in items)
    align = "|".join([":---:"] * len(items))
    images = " | ".join(_image(item) for item in items)
    descs = " | ".join(_desc(item, max_sides) for item in items)
    return f"| {headers} |\n|{align}|\n| {images} |\n| {descs} |"


def format_mattermost_message(menu: DayMenu, source_url: str = "") -> str:
    del source_url
    ordered = {item.course_type: item for item in menu.mains}
    mains = [ordered[code] for code in MAIN_ORDER if code in ordered]
    by_second = {}
    if menu.ramen:
        by_second["DD"] = menu.ramen
    if menu.extra:
        by_second["HH"] = menu.extra
    extras = [by_second[code] for code in SECOND_ORDER if code in by_second]

    parts = ["### :yum: 오늘의 점심 메뉴 :whatistodaylunch:"]
    if mains:
        parts.append(_table(mains, max_sides=None))
    if extras:
        parts.append(_table(extras, max_sides=None))
    return "\n\n".join(part for part in parts if part)
