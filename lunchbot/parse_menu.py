from __future__ import annotations

import re
from dataclasses import dataclass, field


NOISE_EXACT = {
    "keyboard_arrow_right",
    "keyboard_double_arrow_left",
    "연결됨",
    "작성",
    "첫 댓글을 남겨보세요!",
    "댓글 보기/작성",
    "👍 0",
    "👎 0",
}

NOISE_PREFIXES = (
    "Press the down arrow",
    "Selected date is",
    "© ",
    "BOB SSAFY와 함께할",
    "대상:",
    "문의:",
    "광고/제휴",
)


@dataclass
class StationMenu:
    station: str
    name: str
    kcal: str = ""
    rating: str = ""
    items: list[str] = field(default_factory=list)
    image_url: str = ""
    course_type: str = ""


@dataclass
class DayMenu:
    date_label: str
    mains: list[StationMenu] = field(default_factory=list)
    extra: StationMenu | None = None
    ramen: StationMenu | None = None
    raw_text: str = ""

    @property
    def has_content(self) -> bool:
        return bool(self.mains or self.extra or self.ramen)


def _clean_lines(text: str) -> list[str]:
    lines: list[str] = []
    for raw in text.replace("\r\n", "\n").split("\n"):
        line = raw.strip()
        if not line:
            continue
        if line in NOISE_EXACT:
            continue
        if any(line.startswith(prefix) for prefix in NOISE_PREFIXES):
            continue
        if line.startswith("💬"):
            continue
        if re.fullmatch(r"[👍👎]\s*\d+", line):
            continue
        lines.append(line)
    return lines


def _slice_between(lines: list[str], start_pat: str, end_pats: tuple[str, ...]) -> list[str]:
    start = next((i for i, line in enumerate(lines) if re.search(start_pat, line)), None)
    if start is None:
        return []
    rest = lines[start + 1 :]
    end = next((i for i, line in enumerate(rest) if any(re.search(p, line) for p in end_pats)), None)
    return rest if end is None else rest[:end]


def _parse_station_blocks(lines: list[str]) -> list[StationMenu]:
    menus: list[StationMenu] = []
    i = 0
    while i < len(lines):
        station = lines[i]
        if station.startswith("•") or station.startswith("📋") or station.startswith("⭐") or station.startswith("🔥"):
            i += 1
            continue
        if i + 1 >= len(lines):
            break
        name = lines[i + 1]
        if name.startswith("•") or name.startswith("📋"):
            i += 1
            continue

        rating = ""
        kcal = ""
        items: list[str] = []
        j = i + 2
        while j < len(lines):
            line = lines[j]
            if line.startswith("⭐"):
                rating = line.replace("⭐", "").strip()
                j += 1
                continue
            if line.startswith("🔥") or "kcal" in line.lower():
                kcal = re.sub(r"[🔥\s]", "", line)
                j += 1
                continue
            if line.startswith("📋"):
                j += 1
                continue
            if line.startswith("•"):
                items.append(line.lstrip("• ").strip())
                j += 1
                continue
            break
        menus.append(StationMenu(station=station, name=name, kcal=kcal, rating=rating, items=items))
        i = j
    return menus


def parse_menu_text(text: str, date_label: str = "") -> DayMenu:
    lines = _clean_lines(text)
    date_from_page = next((line for line in lines if line.startswith("Selected date is")), "")
    if not date_label and date_from_page:
        date_label = date_from_page.replace("Selected date is", "").split(".")[0].strip()

    main_lines = _slice_between(lines, r"메인 메뉴", (r"추가 배식대", r"라면 메뉴"))
    extra_lines = _slice_between(lines, r"추가 배식대", (r"라면 메뉴",))
    ramen_lines = _slice_between(lines, r"라면 메뉴", ())

    mains = _parse_station_blocks(main_lines)

    extra = None
    if extra_lines:
        extra_name = extra_lines[0]
        extra_items: list[str] = []
        for line in extra_lines[1:]:
            if "구성" in line:
                payload = line.split(":", 1)[-1] if ":" in line else line
                extra_items.extend(part.strip() for part in payload.split("/") if part.strip())
            elif line.startswith("•"):
                extra_items.append(line.lstrip("• ").strip())
        extra = StationMenu(station="추가 배식대", name=extra_name, items=extra_items)

    ramen = None
    if ramen_lines:
        ramen_station = ramen_lines[0]
        ramen_name = ramen_lines[1] if len(ramen_lines) > 1 else ramen_station
        ramen_items = [line.lstrip("• ").strip() for line in ramen_lines[2:] if line.startswith("•")]
        ramen = StationMenu(station=ramen_station, name=ramen_name, items=ramen_items)

    return DayMenu(date_label=date_label, mains=mains, extra=extra, ramen=ramen, raw_text=text)
