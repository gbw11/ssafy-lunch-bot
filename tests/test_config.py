"""웹훅 URL 목록 파싱."""

from __future__ import annotations

from lunchbot.config import load_settings


def _env(monkeypatch, **values) -> None:
    for name in ("MATTERMOST_WEBHOOK_URL", "MATTERMOST_WEBHOOK_URLS"):
        monkeypatch.delenv(name, raising=False)
    for name, value in values.items():
        monkeypatch.setenv(name, value)


def test_single_url_still_works(monkeypatch):
    _env(monkeypatch, MATTERMOST_WEBHOOK_URL="https://mm/hooks/aaa")
    assert load_settings().webhook_urls == ("https://mm/hooks/aaa",)


def test_comma_separated_urls(monkeypatch):
    _env(monkeypatch, MATTERMOST_WEBHOOK_URLS="https://mm/hooks/aaa, https://mm/hooks/bbb")
    assert load_settings().webhook_urls == ("https://mm/hooks/aaa", "https://mm/hooks/bbb")


def test_both_vars_merge_without_duplicates(monkeypatch):
    _env(
        monkeypatch,
        MATTERMOST_WEBHOOK_URLS="https://mm/hooks/aaa,https://mm/hooks/bbb",
        MATTERMOST_WEBHOOK_URL="https://mm/hooks/aaa",
    )
    assert load_settings().webhook_urls == ("https://mm/hooks/aaa", "https://mm/hooks/bbb")


def test_empty_means_no_webhook(monkeypatch):
    _env(monkeypatch, MATTERMOST_WEBHOOK_URLS="  ,  ")
    assert load_settings().webhook_urls == ()
