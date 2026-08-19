from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _env(name: str, default: str = "") -> str:
    value = os.getenv(name)
    if value is None:
        return default
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        value = value[1:-1].strip()
    return value or default


@dataclass(frozen=True)
class Settings:
    bobssafy_url: str
    timezone: str
    webhook_url: str
    channel: str
    channel_id: str
    mattermost_url: str
    mattermost_token: str
    welstory_username: str
    welstory_password: str
    welstory_remember_me: str
    welstory_jsessionid: str
    welstory_campus: str
    welstory_restaurant_code: str
    bobssafy_enabled: bool

    @property
    def can_notify(self) -> bool:
        return bool(self.webhook_url or (self.mattermost_token and self.channel_id))

    @property
    def has_welstory_login(self) -> bool:
        return bool(self.welstory_username and self.welstory_password)

    @property
    def has_welstory_session(self) -> bool:
        return bool(self.welstory_remember_me or self.welstory_jsessionid)

    @property
    def has_welstory(self) -> bool:
        return self.has_welstory_login or self.has_welstory_session


def load_settings() -> Settings:
    url = _env("BOBSSAFY_URL", "https://bobssafy.streamlit.app/").rstrip("/") + "/"
    return Settings(
        bobssafy_url=url,
        timezone=_env("TIMEZONE", "Asia/Seoul"),
        webhook_url=_env("MATTERMOST_WEBHOOK_URL"),
        channel=_env("MATTERMOST_CHANNEL", "간식먹고노라라"),
        channel_id=_env("MATTERMOST_CHANNEL_ID", "9ac0b84f5d7b6f81293023d1245cd537"),
        mattermost_url=_env("MATTERMOST_URL", "https://meeting.ssafy.com").rstrip("/"),
        mattermost_token=_env("MATTERMOST_TOKEN"),
        welstory_username=_env("WELLSTORY_USERNAME") or _env("WELLSTORY_ID"),
        welstory_password=_env("WELLSTORY_PASSWORD"),
        welstory_remember_me=_env("WELLSTORY_REMEMBER_ME"),
        welstory_jsessionid=_env("WELLSTORY_JSESSIONID"),
        welstory_campus=_env("WELLSTORY_CAMPUS"),
        welstory_restaurant_code=_env("WELLSTORY_RESTAURANT_CODE"),
        bobssafy_enabled=_env("BOBSSAFY_ENABLED", "true").lower() not in {"0", "false", "no", "off"},
    )
