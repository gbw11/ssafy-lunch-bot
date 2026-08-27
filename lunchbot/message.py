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


def _menu_text(item: StationMenu) -> str:
    """메뉴 항목을 한 셀에 콤마로 이어 붙입니다.

    열 너비는 사진(240px)이 잡으므로, 길어진 글자는 셀 안에서 다음 줄로 넘어갑니다.
    한글은 공백이 없어도 음절 단위로 줄바꿈되기 때문에 콤마로만 이어도 됩니다
    (Mattermost는 raw HTML을 막아 `<br>` 로 직접 줄을 나눌 수는 없습니다).
    """
    return ",".join(name.strip() for name in (item.name, *item.items) if name.strip())


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
    # 값이 하나도 없는 줄은 빈 칸만 남으므로 그 행 자체를 뺍니다.
    for cell_of in (_image, _menu_text, lambda item: f"**{item.kcal}**" if item.kcal else ""):
        cells = [cell_of(item) for item in items]
        if any(cells):
            rows.append(_row(cells))
    return "\n".join(rows)


def format_message(menu: DayMenu) -> str:
    """메인 코너 표 하나 + 마이보글·추가배식대 표 하나."""
    extras = [item for item in (menu.ramen, menu.extra) if item]
    parts = [HEADING, _table(menu.mains), _table(extras)]
    return "\n\n".join(part for part in parts if part)
