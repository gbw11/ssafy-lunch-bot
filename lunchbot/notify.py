from __future__ import annotations

import json

import requests

from lunchbot.config import Settings


class NotifyError(RuntimeError):
    pass


def send_message(settings: Settings, text: str) -> str:
    if settings.webhook_url:
        return _send_webhook(settings, text)
    if settings.mattermost_token and settings.channel_id:
        return _send_api(settings, text)
    raise NotifyError(
        "알림 설정이 없습니다. MATTERMOST_WEBHOOK_URL 또는 "
        "MATTERMOST_TOKEN + MATTERMOST_CHANNEL_ID 를 넣어 주세요."
    )


def _webhook_payload(text: str) -> dict[str, str]:
    # 채널은 웹훅을 만들 때 지정한 곳으로 갑니다.
    # 표시 이름(간식먹고노라라)을 channel에 넣으면 404가 나는 경우가 많습니다.
    return {
        "text": text,
        "username": "급식봇",
        "icon_emoji": ":bento:",
    }


def _is_ok(response: requests.Response) -> bool:
    if response.status_code >= 300:
        return False
    body = response.text.strip()
    return body in {"ok", ""} or body.startswith("{")


def _send_webhook(settings: Settings, text: str) -> str:
    payload = _webhook_payload(text)
    encoded = json.dumps(payload, ensure_ascii=False)

    # SSAFY Mattermost는 application/json을 거절하고 form payload만 받는 경우가 있습니다.
    form_response = requests.post(
        settings.webhook_url,
        data={"payload": encoded},
        timeout=20,
    )
    if _is_ok(form_response):
        return "webhook"

    json_response = requests.post(
        settings.webhook_url,
        data=encoded.encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        timeout=20,
    )
    if _is_ok(json_response):
        return "webhook"

    raise NotifyError(
        "웹훅 전송 실패 "
        f"(form {form_response.status_code}: {form_response.text[:200]} / "
        f"json {json_response.status_code}: {json_response.text[:200]})"
    )


def _send_api(settings: Settings, text: str) -> str:
    url = f"{settings.mattermost_url}/api/v4/posts"
    headers = {
        "Authorization": f"Bearer {settings.mattermost_token}",
        "Content-Type": "application/json",
    }
    payload = {"channel_id": settings.channel_id, "message": text}
    response = requests.post(url, json=payload, headers=headers, timeout=20)
    if response.status_code >= 300:
        raise NotifyError(f"Mattermost API 전송 실패 ({response.status_code}): {response.text[:300]}")
    return "api"
