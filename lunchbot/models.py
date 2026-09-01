"""메뉴 데이터 모델과 시간 헬퍼."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DEFAULT_TIMEZONE = "Asia/Seoul"
KST = timezone(timedelta(hours=9))
MENU_KEY_STRIP_RE = re.compile(r"[^0-9A-Za-z가-힣]+")


def menu_key(text: str) -> str:
    """메뉴명으로 코너를 짝지을 때 쓰는 키.

    소스마다 같은 메뉴를 `[테이스티가든]_연어구이` / `[테이스티가든]연어구이` 처럼
    기호만 다르게 쓰기 때문에 한글·영숫자만 남깁니다.
    """
    return MENU_KEY_STRIP_RE.sub("", str(text or "")).lower()


def now_in(name: str = DEFAULT_TIMEZONE) -> datetime:
    try:
        tz = ZoneInfo(name)
    except ZoneInfoNotFoundError:
        tz = KST
    return datetime.now(tz)


@dataclass
class StationMenu:
    """코너 하나의 당일 메뉴."""

    station: str
    name: str
    kcal: str = ""
    items: list[str] = field(default_factory=list)
    image_url: str = ""
    course_type: str = ""

    def photo_keys(self) -> list[str]:
        """이 코너의 사진을 찾을 때 써 볼 키들. 코너코드 → 코너명 → 메뉴명 순."""
        joined = ",".join(name.strip() for name in (self.name, *self.items) if name.strip())
        keys = (self.course_type, self.station, menu_key(self.name), menu_key(joined))
        return [key for key in keys if key]


@dataclass
class DayMenu:
    date_label: str
    mains: list[StationMenu] = field(default_factory=list)
    ramen: StationMenu | None = None
    extra: StationMenu | None = None

    @property
    def stations(self) -> list[StationMenu]:
        """메인 코너 + 마이보글 + 추가배식대 중 있는 것만."""
        return [item for item in (*self.mains, self.ramen, self.extra) if item]

    @property
    def has_content(self) -> bool:
        return bool(self.stations)

    def fill_photos(
        self,
        photos: dict[str, str],
        needs_photo: Callable[[StationMenu], bool],
    ) -> None:
        """사진이 필요한 코너를 photos(코너코드·코너명·메뉴명 → URL)로 채웁니다."""
        for item in self.stations:
            if not needs_photo(item):
                continue
            for key in item.photo_keys():
                photo = photos.get(key)
                if photo:
                    item.image_url = photo
                    break
