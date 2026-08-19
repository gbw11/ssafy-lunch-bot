"""환경변수(.env) 설정."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

from lunchbot.models import DEFAULT_TIMEZONE

load_dotenv()

FALSY = {"0", "false", "no", "off"}


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
    welstory_remember_me: str
    welstory_jsessionid: str
    welstory_campus: str
    welstory_restaurant_code: str
    bobssafy_url: str
    bobssafy_enabled: bool

    @property
    def has_welstory_login(self) -> bool:
        return bool(self.welstory_username and self.welstory_password)

    @property
    def has_welstory(self) -> bool:
        return bool(
            self.has_welstory_login
            or self.welstory_remember_me
            or self.welstory_jsessionid
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
        welstory_remember_me=_env("WELLSTORY_REMEMBER_ME"),
        welstory_jsessionid=_env("WELLSTORY_JSESSIONID"),
        welstory_campus=_env("WELLSTORY_CAMPUS"),
        welstory_restaurant_code=_env("WELLSTORY_RESTAURANT_CODE"),
        bobssafy_url=_env("BOBSSAFY_URL", "https://bobssafy.streamlit.app/").rstrip("/") + "/",
        bobssafy_enabled=_env("BOBSSAFY_ENABLED", "true").lower() not in FALSY,
    )
