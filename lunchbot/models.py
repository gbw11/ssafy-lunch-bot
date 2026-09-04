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
# 반찬 이름 득표로 사진을 붙이려면 최소 이만큼은 겹쳐야 합니다.
MIN_DISH_VOTES = 2


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
class PhotoSet:
    """사진 소스 하나의 결과.

    `by_key` 는 코너코드·코너명·메뉴명 → URL 로 정확 일치용이고, `dishes` 는
    URL → 그 사진에 딸린 반찬 이름 키들로 정확 일치가 실패했을 때 득표용입니다.
    `dishes` 를 못 주는 소스는 `PhotoSet.of()` 로 감싸면 기존처럼 정확 일치만 씁니다.
    """

    by_key: dict[str, str] = field(default_factory=dict)
    dishes: dict[str, frozenset[str]] = field(default_factory=dict)

    @classmethod
    def of(cls, photos) -> "PhotoSet":
        return photos if isinstance(photos, cls) else cls(by_key=dict(photos or {}))


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

    def dish_keys(self) -> frozenset[str]:
        """대표 메뉴 + 반찬 이름 키들. 정확 일치가 실패했을 때 득표로 짝지을 때 씁니다."""
        return frozenset(
            key for key in (menu_key(name) for name in (self.name, *self.items)) if key
        )


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
        photos,
        needs_photo: Callable[[StationMenu], bool],
    ) -> None:
        """사진이 필요한 코너를 채웁니다. 정확 일치를 먼저 다 쓰고 득표로 넘어갑니다."""
        photo_set = PhotoSet.of(photos)
        for item in self.stations:
            if not needs_photo(item):
                continue
            for key in item.photo_keys():
                photo = photo_set.by_key.get(key)
                if photo:
                    item.image_url = photo
                    break
        self._fill_photos_by_votes(photo_set, needs_photo)

    def _fill_photos_by_votes(
        self,
        photo_set: PhotoSet,
        needs_photo: Callable[[StationMenu], bool],
    ) -> None:
        """대표 메뉴명이 소스끼리 어긋난 코너를 반찬 이름 겹침으로 짝지웁니다.

        소스가 `돈육순두부찌개` 를 `돈육두부찌개` 로 쓰는 날처럼 대표명 한 글자가
        달라도 반찬 구성은 그대로라, 겹치는 반찬 수로 고를 수 있습니다. 다만
        `흰쌀밥` 처럼 여러 코너에 겹치는 이름이 있어 틀린 사진을 붙일 위험이
        있으므로, **2표 이상 + 단독 1위** 일 때만 붙이고 애매하면 비워 둡니다.
        틀린 사진은 사진이 없는 것보다 나쁩니다.
        """
        if not photo_set.dishes:
            return
        used = {item.image_url for item in self.stations if item.image_url}
        for item in self.stations:
            if not needs_photo(item):
                continue
            keys = item.dish_keys()
            if not keys:
                continue
            scored = sorted(
                (
                    (len(keys & dish_keys), url)
                    for url, dish_keys in photo_set.dishes.items()
                    if url not in used
                ),
                reverse=True,
            )
            if not scored or scored[0][0] < MIN_DISH_VOTES:
                continue
            if len(scored) > 1 and scored[1][0] == scored[0][0]:
                continue  # 동점이면 어느 쪽인지 알 수 없어 비워 둡니다.
            item.image_url = scored[0][1]
            used.add(scored[0][1])
