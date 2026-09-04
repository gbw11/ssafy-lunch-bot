"""주말·공휴일 스킵 테스트."""

from __future__ import annotations

from datetime import date, datetime

import pytest

from lunchbot import workdays


@pytest.mark.parametrize(
    "day",
    [
        date(2026, 9, 4),   # 금요일
        date(2026, 9, 7),   # 월요일
        date(2026, 7, 17),  # 제헌절 — 2008년부터 공휴일이 아니라 급식이 있습니다.
    ],
)
def test_workday_sends(day: date) -> None:
    assert workdays.skip_reason(day) == ""


@pytest.mark.parametrize("day", [date(2026, 9, 5), date(2026, 9, 6)])
def test_weekend_is_skipped(day: date) -> None:
    assert workdays.skip_reason(day) == "주말"


@pytest.mark.parametrize(
    "day",
    [
        date(2026, 1, 1),   # 신정
        date(2026, 2, 17),  # 설날 — 음력이라 해마다 날짜가 다릅니다.
        date(2026, 9, 25),  # 추석
        date(2026, 3, 2),   # 삼일절 대체공휴일
        date(2026, 5, 25),  # 부처님오신날 대체공휴일
        date(2026, 5, 1),   # 근로자의날
    ],
)
def test_holiday_is_skipped(day: date) -> None:
    assert workdays.skip_reason(day).startswith("공휴일(")


def test_weekend_wins_over_holiday_naming() -> None:
    """토요일에 걸린 공휴일도 이유는 주말로 충분합니다."""
    assert workdays.skip_reason(date(2026, 10, 3)) == "주말"  # 개천절(토)


def test_accepts_datetime() -> None:
    assert workdays.skip_reason(datetime(2026, 9, 5, 10, 39)) == "주말"
    assert workdays.skip_reason(datetime(2026, 9, 4, 10, 39)) == ""


def test_holiday_name_is_empty_on_a_workday() -> None:
    assert workdays.holiday_name(date(2026, 9, 4)) == ""
    assert workdays.holiday_name(date(2026, 2, 17)) != ""
