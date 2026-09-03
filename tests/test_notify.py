"""여러 방(웹훅)으로 보내는 전송 테스트."""

from __future__ import annotations

import pytest
import requests

from lunchbot import notify
from tests.test_main import _settings

OK = "https://mm.example/hooks/aaaaaa"
BAD = "https://mm.example/hooks/bbbbbb"


class _Response:
    def __init__(self, status_code: int, text: str = "ok") -> None:
        self.status_code = status_code
        self.text = text


def _fake_post(calls: list[str], *, failing: set[str] = frozenset()):
    def post(url, **kwargs):
        calls.append(url)
        if url in failing:
            return _Response(500, "boom")
        return _Response(200)

    return post


def test_sends_to_every_webhook(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(notify.requests, "post", _fake_post(calls))

    result = notify.send_message(_settings(webhook_urls=(OK, BAD)), "메뉴")

    assert result.ok
    assert calls == [OK, BAD]
    assert str(result) == "webhook 2곳"


def test_one_room_failing_does_not_stop_the_others(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(notify.requests, "post", _fake_post(calls, failing={OK}))

    result = notify.send_message(_settings(webhook_urls=(OK, BAD)), "메뉴")

    assert not result.ok
    assert BAD in calls  # 앞 방이 실패해도 뒷 방에는 보냅니다.
    assert str(result) == "webhook 1/2곳"
    assert "aaaaaa" in result.failures[0]


def test_all_failing_raises(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(
        notify.requests, "post", _fake_post(calls, failing={OK, BAD})
    )

    with pytest.raises(notify.NotifyError):
        notify.send_message(_settings(webhook_urls=(OK, BAD)), "메뉴")


def test_network_error_is_one_room_failure(monkeypatch):
    def post(url, **kwargs):
        if url == OK:
            raise requests.ConnectionError("끊김")
        return _Response(200)

    monkeypatch.setattr(notify.requests, "post", post)

    result = notify.send_message(_settings(webhook_urls=(OK, BAD)), "메뉴")

    assert not result.ok and str(result) == "webhook 1/2곳"
