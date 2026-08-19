"""Mattermost 전송 (웹훅 우선, 없으면 API 토큰)."""

from __future__ import annotations

import json

import requests

from lunchbot.config import Settings

TIMEOUT = 20
BOT_NAME = "급식봇"
BOT_ICON = ":bento:"


class NotifyError(RuntimeError):
    pass


def _is_ok(response: requests.Response) -> bool:
    if response.status_code >= 300:
        return False
    body = response.text.strip()
    return body in {"ok", ""} or body.startswith("{")


def _send_webhook(webhook_url: str, text: str) -> str:
    # 채널은 웹훅을 만들 때 지정한 곳으로 갑니다. 표시 이름을 channel에 넣으면 404가 나기 쉽습니다.
    payload = json.dumps(
        {"text": text, "username": BOT_NAME, "icon_emoji": BOT_ICON},
        ensure_ascii=False,
    )

    # SSAFY Mattermost는 application/json을 거절하고 form payload만 받는 경우가 있습니다.
    attempts = [
        {"data": {"payload": payload}},
        {
            "data": payload.encode("utf-8"),
            "headers": {"Content-Type": "application/json; charset=utf-8"},
        },
    ]
    failures = []
    for kwargs in attempts:
        response = requests.post(webhook_url, timeout=TIMEOUT, **kwargs)
        if _is_ok(response):
            return "webhook"
        failures.append(f"{response.status_code}: {response.text[:200]}")
    raise NotifyError("웹훅 전송 실패 (form " + " / json ".join(failures) + ")")


def _send_api(settings: Settings, text: str) -> str:
    response = requests.post(
        f"{settings.mattermost_url}/api/v4/posts",
        json={"channel_id": settings.channel_id, "message": text},
        headers={
            "Authorization": f"Bearer {settings.mattermost_token}",
            "Content-Type": "application/json",
        },
        timeout=TIMEOUT,
    )
    if response.status_code >= 300:
        raise NotifyError(
            f"Mattermost API 전송 실패 ({response.status_code}): {response.text[:300]}"
        )
    return "api"


def send_message(settings: Settings, text: str) -> str:
    """전송에 쓴 방법('webhook' 또는 'api')을 돌려줍니다."""
    if settings.webhook_url:
        return _send_webhook(settings.webhook_url, text)
    if settings.mattermost_token and settings.channel_id:
        return _send_api(settings, text)
    raise NotifyError(
        "알림 설정이 없습니다. MATTERMOST_WEBHOOK_URL 또는 "
        "MATTERMOST_TOKEN + MATTERMOST_CHANNEL_ID 를 넣어 주세요."
    )
