"""환경변수(.env) 설정."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

from lunchbot.models import DEFAULT_TIMEZONE

load_dotenv()

FALSY = {"0", "false", "no", "off"}

# 실제 점심 사진은 배식 직전(대개 10:30 전후)에야 웰스토리에 올라옵니다.
# 그전에는 플레이스홀더뿐이라 잠시 기다렸다 다시 조회합니다.
DEFAULT_PHOTO_WAIT_MINUTES = "25"
DEFAULT_PHOTO_POLL_SECONDS = "60"


def _int_env(name: str, default: str) -> int:
    try:
        return max(0, int(_env(name, default)))
    except ValueError:
        return int(default)


def _env(name: str, default: str = "") -> str:
    value = (os.getenv(name) or "").strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        value = value[1:-1].strip()
    return value or default


@dataclass(frozen=True)
class Settings:
    timezone: str
    webhook_url: str
    channel_id: str
    mattermost_url: str
    mattermost_token: str
    welstory_username: str
    welstory_password: str
    welstory_access_token: str
    welstory_device_id: str
    welstory_remember_me: str
    welstory_jsessionid: str
    welstory_campus: str
    welstory_restaurant_code: str
    mealcloud_url: str
    mealcloud_enabled: bool
    photo_wait_seconds: int
    photo_poll_seconds: int

    @property
    def has_welstory_login(self) -> bool:
        return bool(self.welstory_username and self.welstory_password)

    @property
    def has_welstory_session(self) -> bool:
        """브라우저에서 받아온 토큰·쿠키가 있으면 WAF에 막히는 로그인을 건너뜁니다."""
        return bool(
            self.welstory_access_token
            or self.welstory_remember_me
            or self.welstory_jsessionid
        )

    @property
    def has_welstory(self) -> bool:
        return bool(
            self.has_welstory_login
            or self.has_welstory_session
        )


def load_settings() -> Settings:
    return Settings(
        timezone=_env("TIMEZONE", DEFAULT_TIMEZONE),
        webhook_url=_env("MATTERMOST_WEBHOOK_URL"),
        channel_id=_env("MATTERMOST_CHANNEL_ID", "9ac0b84f5d7b6f81293023d1245cd537"),
        mattermost_url=_env("MATTERMOST_URL", "https://meeting.ssafy.com").rstrip("/"),
        mattermost_token=_env("MATTERMOST_TOKEN"),
        welstory_username=_env("WELLSTORY_USERNAME") or _env("WELLSTORY_ID"),
        welstory_password=_env("WELLSTORY_PASSWORD"),
        welstory_access_token=_env("WELLSTORY_ACCESS_TOKEN"),
        welstory_device_id=_env("WELLSTORY_DEVICE_ID"),
        welstory_remember_me=_env("WELLSTORY_REMEMBER_ME"),
        welstory_jsessionid=_env("WELLSTORY_JSESSIONID"),
        welstory_campus=_env("WELLSTORY_CAMPUS"),
        welstory_restaurant_code=_env("WELLSTORY_RESTAURANT_CODE"),
        mealcloud_url=_env("MEALCLOUD_URL", "https://welstory-meal.cloud").rstrip("/"),
        mealcloud_enabled=_env("MEALCLOUD_ENABLED", "true").lower() not in FALSY,
        photo_wait_seconds=_int_env("PHOTO_WAIT_MINUTES", DEFAULT_PHOTO_WAIT_MINUTES) * 60,
        photo_poll_seconds=_int_env("PHOTO_POLL_SECONDS", DEFAULT_PHOTO_POLL_SECONDS) or 60,
    )
