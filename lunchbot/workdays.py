"""급식이 없는 날 판정. 주말·공휴일에는 메시지를 보내지 않습니다."""

from __future__ import annotations

from datetime import date, datetime
from functools import lru_cache

import holidays

# 설날·추석·부처님오신날은 음력이라 해마다 날짜가 달라서 직접 적어두면 매년 깨집니다.
# `holidays` 패키지가 음력 명절과 대체공휴일까지 계산해 주므로 그걸 씁니다.
COUNTRY = "KR"

# holidays 0.103 은 제헌절(7/17)을 public 공휴일로 주는데, 2008년부터 쉬는 날이
# 아닙니다. 이름은 패키지 버전마다 바뀔 수 있어 날짜로 걸러냅니다.
WORKING_HOLIDAYS = frozenset({(7, 17)})


@lru_cache(maxsize=8)
def _holidays(year: int):
    # 로그에 그대로 찍히므로 공휴일 이름도 한국어로 받습니다.
    return holidays.country_holidays(COUNTRY, years=year, language="ko")


def holiday_name(day: date) -> str:
    """그 날의 공휴일 이름. 공휴일이 아니면 빈 문자열."""
    if (day.month, day.day) in WORKING_HOLIDAYS:
        return ""
    return _holidays(day.year).get(day) or ""


def skip_reason(day: datetime | date) -> str:
    """메시지를 보내지 않을 이유. 보내야 하는 날이면 빈 문자열.

    주말은 급식이 없고, 공휴일도 마찬가지입니다. 근로자의날(5/1)처럼 관공서만
    쉬는 날도 사업장 급식은 함께 쉬므로 공휴일로 함께 봅니다.
    """
    if isinstance(day, datetime):
        day = day.date()
    if day.weekday() >= 5:
        return "주말"
    name = holiday_name(day)
    return f"공휴일({name})" if name else ""
