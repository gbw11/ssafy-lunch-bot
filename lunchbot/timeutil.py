from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

KST = timezone(timedelta(hours=9))


def zone(name: str = "Asia/Seoul"):
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        return KST


def now_in(name: str = "Asia/Seoul") -> datetime:
    return datetime.now(zone(name))
