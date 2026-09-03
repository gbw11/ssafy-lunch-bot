"""사진 대기 루프 테스트."""

from __future__ import annotations

import lunchbot.__main__ as cli
from lunchbot.config import Settings
from lunchbot.models import DayMenu, StationMenu

PLACEHOLDER = "https://img-welmenu.welstory.com/s20260821123252.jpg"
REAL = "https://img-welmenu.welstory.com/s20260826103012.jpg"


def _settings(**overrides) -> Settings:
    base = dict(
        timezone="Asia/Seoul", webhook_urls=(), channel_id="", mattermost_url="",
        mattermost_token="", welstory_username="", welstory_password="",
        welstory_access_token="", welstory_device_id="",
        welstory_remember_me="", welstory_jsessionid="", welstory_campus="",
        welstory_restaurant_code="", mealcloud_url="", mealcloud_enabled=False,
        photo_wait_seconds=300, photo_poll_seconds=60,
    )
    return Settings(**{**base, **overrides})


def _menu(url: str = PLACEHOLDER) -> DayMenu:
    return DayMenu(
        date_label="2026-08-26",
        mains=[StationMenu(station="브라운그릴", name="불고기", image_url=url, course_type="A1")],
    )


def _patch(monkeypatch, *, real_urls: set[str], photo_rounds: list[dict]) -> list[int]:
    """time.sleep을 가짜 시계로 바꿔 대기 루프를 즉시 돌립니다."""
    slept: list[int] = []
    clock = [0.0]

    def fake_sleep(seconds: float) -> None:
        slept.append(seconds)
        clock[0] += seconds

    monkeypatch.setattr(cli.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(cli.time, "sleep", fake_sleep)
    monkeypatch.setattr(cli.welplan, "is_real_menu_image", lambda url: url in real_urls)
    rounds = iter(photo_rounds)
    monkeypatch.setattr(
        cli.welplan, "fetch_live_photos", lambda code, date: next(rounds, {})
    )
    return slept


def test_wait_stops_as_soon_as_real_photo_appears(monkeypatch) -> None:
    menu = _menu()
    slept = _patch(monkeypatch, real_urls={REAL}, photo_rounds=[{"A1": REAL}])
    cli._wait_for_lunch_photos(menu, _settings(), "REST000595", [])
    assert menu.mains[0].image_url == REAL
    assert slept == [60]  # 한 번만 기다리고 빠져나옵니다.


def test_wait_gives_up_after_the_limit(monkeypatch) -> None:
    menu = _menu()
    slept = _patch(monkeypatch, real_urls=set(), photo_rounds=[])
    cli._wait_for_lunch_photos(menu, _settings(photo_wait_seconds=180), "REST000595", [])
    assert menu.mains[0].image_url == PLACEHOLDER  # _warn_missing_photos가 나중에 비웁니다.
    assert sum(slept) == 180


def test_wait_is_skipped_when_photos_are_already_real(monkeypatch) -> None:
    menu = _menu(REAL)
    slept = _patch(monkeypatch, real_urls={REAL}, photo_rounds=[])
    cli._wait_for_lunch_photos(menu, _settings(), "REST000595", [])
    assert slept == []


def test_wait_disabled_by_zero_minutes(monkeypatch) -> None:
    menu = _menu()
    slept = _patch(monkeypatch, real_urls=set(), photo_rounds=[])
    cli._wait_for_lunch_photos(menu, _settings(photo_wait_seconds=0), "REST000595", [])
    assert slept == []


def _labels(settings: Settings) -> list[str]:
    return [label for label, _fetch, _error in cli._photo_sources(settings, "REST000595")]


def test_cookie_puts_welstory_before_the_fallback() -> None:
    settings = _settings(welstory_remember_me="abc", mealcloud_enabled=True)
    assert _labels(settings) == ["웰스토리(remember-me 쿠키)", "welstory-meal.cloud"]


def test_access_token_puts_welstory_before_the_fallback() -> None:
    settings = _settings(welstory_access_token="tok", mealcloud_enabled=True)
    assert _labels(settings) == ["웰스토리(accessToken(Bearer))", "welstory-meal.cloud"]


def test_id_pw_login_is_tried_last_because_the_waf_blocks_it() -> None:
    settings = _settings(
        welstory_username="me", welstory_password="pw", mealcloud_enabled=True
    )
    labels = _labels(settings)
    assert labels[0] == "welstory-meal.cloud"
    assert labels[1].startswith("웰스토리(ID/PW 로그인")


def test_no_welstory_auth_means_fallback_only() -> None:
    assert _labels(_settings(mealcloud_enabled=True)) == ["welstory-meal.cloud"]


def test_first_source_with_a_photo_wins(monkeypatch) -> None:
    menu = _menu("")
    monkeypatch.setattr(cli.welplan, "is_real_menu_image", lambda url: bool(url))
    calls: list[str] = []

    def source(label: str, photos: dict[str, str]) -> cli.PhotoSource:
        def fetch() -> dict[str, str]:
            calls.append(label)
            return photos

        return (label, fetch, RuntimeError)

    cli._fill_from_sources(menu, [source("first", {"A1": REAL}), source("second", {"A1": "x"})])

    assert menu.mains[0].image_url == REAL
    assert calls == ["first"]  # 다 채워졌으면 다음 소스는 아예 안 부릅니다.
