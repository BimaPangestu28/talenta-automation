from datetime import datetime
from zoneinfo import ZoneInfo

import httpx

from talenta_bot.notifier import TelegramNotifier, build_message

TS = datetime(2026, 4, 16, 8, 7, 12, tzinfo=ZoneInfo("Asia/Jakarta"))


def test_success_message():
    msg = build_message(kind="success", action="Clock In", ts=TS)
    assert msg.startswith("✅ Clock In 08:07 WIB")
    assert "Talenta OK" in msg


def test_info_skipped_message():
    msg = build_message(
        kind="info", action="Clock In", ts=TS, note="tercatat 07:52 WIB (manual)"
    )
    assert msg.startswith("ℹ️ Clock In")
    assert "tercatat 07:52 WIB" in msg


def test_warning_with_reason():
    msg = build_message(
        kind="warning",
        action="Clock In",
        ts=TS,
        category="TalentaDown",
        reason="goto timeout 10s",
    )
    assert msg.startswith("⚠️")
    assert "TalentaDown" in msg
    assert "goto timeout 10s" in msg


def test_critical_includes_category():
    msg = build_message(
        kind="critical",
        action="Clock In",
        ts=TS,
        category="LoginFailed",
        reason="Email atau password salah",
    )
    assert msg.startswith("🚨")
    assert "LoginFailed" in msg
    assert "Email atau password salah" in msg


def _resp(url: str, status: int, **kwargs) -> httpx.Response:
    return httpx.Response(status, request=httpx.Request("POST", url), **kwargs)


def test_send_text_calls_bot_api(monkeypatch):
    captured: dict = {}

    def fake_post(url, data=None, timeout=None, **_kwargs):
        captured["url"] = url
        captured["data"] = data
        return _resp(url, 200, json={"ok": True})

    monkeypatch.setattr(httpx, "post", fake_post)

    ok = TelegramNotifier("123:abc", "42").send_text("hi")
    assert ok is True
    assert captured["url"] == "https://api.telegram.org/bot123:abc/sendMessage"
    assert captured["data"] == {"chat_id": "42", "text": "hi"}


def test_send_text_returns_false_on_http_error(monkeypatch):
    def fake_post(url, data=None, timeout=None, **_kwargs):
        return _resp(url, 500)

    monkeypatch.setattr(httpx, "post", fake_post)
    assert TelegramNotifier("123:abc", "42").send_text("hi") is False
