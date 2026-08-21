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


def _desc(item: StationMenu) -> str:
    text = ",".join(name.strip() for name in (item.name, *item.items) if name.strip())
    if item.kcal:
        kcal = item.kcal.replace("kcal", "")
        text = f"{text} ({kcal}kcal)" if text else f"({kcal}kcal)"
    return text


def _image_table(items: list[StationMenu]) -> str:
    """코너명 + 사진만 있는 표. 메뉴 글 길이가 이 표의 열 너비에 영향을 주지 않도록 분리."""
    if not items:
        return ""
    headers = " | ".join(f"**{item.station}**" for item in items)
    align = "|".join([":---:"] * len(items))
    images = " | ".join(_image(item) for item in items)
    return f"| {headers} |\n|{align}|\n| {images} |"


def _desc_list(items: list[StationMenu]) -> str:
    """코너별 메뉴 글을 표 밖에서 목록으로 표시."""
    return "\n".join(f"- **{item.station}**: {_desc(item)}" for item in items if _desc(item))


def _section(items: list[StationMenu]) -> str:
    parts = [_image_table(items), _desc_list(items)]
    return "\n\n".join(part for part in parts if part)


def format_message(menu: DayMenu) -> str:
    """메인 코너 섹션 하나 + 마이보글·추가배식대 섹션 하나."""
    extras = [item for item in (menu.ramen, menu.extra) if item]
    parts = [HEADING, _section(menu.mains), _section(extras)]
    return "\n\n".join(part for part in parts if part)
