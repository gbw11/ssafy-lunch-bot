"""Mattermost로 보낼 마크다운 메시지."""

from __future__ import annotations

from lunchbot.models import DayMenu, StationMenu

HEADING = "### :yum: 오늘의 점심 메뉴 :whatistodaylunch:"

# 사진 소스(welplan / BOB SSAFY / 웰스토리)마다 원본 크기가 달라서
# Mattermost 이미지 크기 문법 `![](url =WxH)` 으로 4:3 한 크기로 맞춥니다.
IMAGE_WIDTH = 240
IMAGE_HEIGHT = 180


def _image(item: StationMenu) -> str:
    if not item.image_url:
        return ""
    return f"![]({item.image_url} ={IMAGE_WIDTH}x{IMAGE_HEIGHT})"


def _split_label(name: str) -> list[str]:
    """'[임직원인기메뉴] 반반불고기덮밥' 처럼 앞에 붙은 분류 라벨은 줄을 나눕니다.

    실제 데이터에서 가장 긴 셀이 이 이름들입니다. 붙여두면 그 열만 사진보다 넓어져
    _menu_lines 가 막으려는 문제가 그대로 재발합니다.
    """
    if not name:
        return []
    if name.startswith("[") and "]" in name:
        label, _, rest = name.partition("]")
        rest = rest.strip()
        if rest:
            return [f"{label}]", rest]
    return [name]


def _menu_lines(item: StationMenu) -> list[str]:
    """한 셀에 몰아넣지 않고, 표의 행을 늘려 메뉴를 한 줄에 하나씩 넣습니다.

    콤마로 이어 붙이면 글자 수가 많은 열만 넓어집니다. 그러면 좁아진 나머지 열의 사진이
    Mattermost의 `max-width:100%` 에 걸려 240px보다 작게 렌더되고, 코너별로 사진 크기가
    달라 보입니다(`=240x180` 을 줘도 마찬가지). 항목을 한 줄씩 끊으면 어느 셀도 사진보다
    넓어지지 않아서 열 너비를 사진이 결정하고, 결과적으로 사진이 전부 같은 크기가 됩니다.
    Mattermost는 `<br>` 같은 raw HTML을 지원하지 않아 셀 안에서는 줄바꿈을 못 합니다.
    """
    lines: list[str] = []
    for name in (item.name, *item.items):
        lines.extend(_split_label(name.strip()))
    return lines


def _row(cells: list[str]) -> str:
    return "| " + " | ".join(cells) + " |"


def _table(items: list[StationMenu]) -> str:
    """코너를 가로로 늘어놓고, 사진 칸 바로 아래에 메뉴와 열량을 넣은 표."""
    if not items:
        return ""
    rows = [
        _row([f"**{item.station}**" for item in items]),
        "|" + "|".join([":---:"] * len(items)) + "|",
    ]
    # 사진이 하나도 없으면 빈 칸만 남은 줄이 되므로 사진 행은 아예 뺍니다.
    if any(item.image_url for item in items):
        rows.append(_row([_image(item) for item in items]))
    columns = [_menu_lines(item) for item in items]
    for line in range(max(len(column) for column in columns)):
        rows.append(_row([column[line] if line < len(column) else "" for column in columns]))
    if any(item.kcal for item in items):
        rows.append(_row([f"**{item.kcal}**" if item.kcal else "" for item in items]))
    return "\n".join(rows)


def format_message(menu: DayMenu) -> str:
    """메인 코너 표 하나 + 마이보글·추가배식대 표 하나."""
    extras = [item for item in (menu.ramen, menu.extra) if item]
    parts = [HEADING, _table(menu.mains), _table(extras)]
    return "\n\n".join(part for part in parts if part)
