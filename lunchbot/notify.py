"""Mattermost 전송 (웹훅 우선, 없으면 API 토큰)."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass

import requests

from lunchbot.config import Settings

TIMEOUT = 20
BOT_NAME = "급식봇"
BOT_ICON = ":bento:"


class NotifyError(RuntimeError):
    pass


@dataclass(frozen=True)
class SendResult:
    """어디로 어떻게 보냈는지. 일부 방만 실패한 경우를 호출한 쪽이 알 수 있게 합니다."""

    summary: str
    failures: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.failures

    def __str__(self) -> str:
        return self.summary


def _is_ok(response: requests.Response) -> bool:
    if response.status_code >= 300:
        return False
    body = response.text.strip()
    return body in {"ok", ""} or body.startswith("{")


def _mask(webhook_url: str) -> str:
    """로그에 URL 전체를 남기지 않도록 뒤 6자만 보여 줍니다."""
    tail = webhook_url.rstrip("/").rsplit("/", 1)[-1]
    return f"...{tail[-6:]}" if tail else "(빈 URL)"


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


def _send_api(settings: Settings, text: str) -> SendResult:
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
    return SendResult("api")


def _send_all_webhooks(webhook_urls: tuple[str, ...], text: str) -> SendResult:
    """방마다 웹훅이 따로라 하나씩 보냅니다. 한 방이 실패해도 나머지는 계속 보냅니다."""
    failures = []
    sent = 0
    for index, url in enumerate(webhook_urls, start=1):
        try:
            _send_webhook(url, text)
        except (NotifyError, requests.RequestException) as exc:
            failures.append(f"#{index} {_mask(url)} — {exc}")
        else:
            sent += 1
    total = len(webhook_urls)
    if not sent:
        raise NotifyError(f"웹훅 {total}곳 모두 전송 실패: " + " / ".join(failures))
    if failures:
        # 일부만 실패해도 나머지 방에는 이미 나갔으니 예외 대신 경고로 남깁니다.
        print("웹훅 일부 전송 실패: " + " / ".join(failures), file=sys.stderr)
        return SendResult(f"webhook {sent}/{total}곳", tuple(failures))
    return SendResult(f"webhook {sent}곳" if total > 1 else "webhook")


def send_message(settings: Settings, text: str) -> SendResult:
    """전송 결과. 웹훅이 여러 개면 하나도 못 보냈을 때만 예외가 납니다."""
    if settings.webhook_urls:
        return _send_all_webhooks(settings.webhook_urls, text)
    if settings.mattermost_token and settings.channel_id:
        return _send_api(settings, text)
    raise NotifyError(
        "알림 설정이 없습니다. MATTERMOST_WEBHOOK_URLS(방이 여러 개면 콤마로 구분) 또는 "
        "MATTERMOST_TOKEN + MATTERMOST_CHANNEL_ID 를 넣어 주세요."
    )
