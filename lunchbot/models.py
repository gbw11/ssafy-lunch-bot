"""메뉴 데이터 모델과 시간 헬퍼."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DEFAULT_TIMEZONE = "Asia/Seoul"
KST = timezone(timedelta(hours=9))


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
        """사진이 필요한 코너를 photos(코너코드 또는 코너명 → URL)로 채웁니다."""
        for item in self.stations:
            if not needs_photo(item):
                continue
            photo = photos.get(item.course_type) or photos.get(item.station)
            if photo:
                item.image_url = photo
