import os

import pytest

from talenta_bot import cli, selectors


@pytest.mark.skipif(
    not os.environ.get("RUN_INTEGRATION"),
    reason="set RUN_INTEGRATION=1 to run — needs Chromium installed",
)
def test_clock_in_flow_against_mock(mock_talenta, tmp_path, monkeypatch):
    server, base = mock_talenta

    monkeypatch.setattr(selectors, "SSO_LOGIN_URL", f"{base}/users/sign_in")
    monkeypatch.setattr(selectors, "TALENTA_BASE_URL", base)
    monkeypatch.setattr(selectors, "LIVE_ATTENDANCE_URL", f"{base}/live-attendance")
    monkeypatch.setattr(selectors, "DASHBOARD_URL_PATTERN", f"{base}/**")

    for k, v in {
        "MEKARI_EMAIL": "x@example.com",
        "MEKARI_PASSWORD": "pw",
        "OFFICE_LAT": "-6.2",
        "OFFICE_LONG": "106.8",
        "GEO_JITTER_METERS": "0",
        "CLOCK_IN_WINDOW_START": "00:00",
        "CLOCK_IN_WINDOW_END": "23:59",
        "CLOCK_OUT_WINDOW_START": "00:00",
        "CLOCK_OUT_WINDOW_END": "23:59",
        "TIMEZONE": "Asia/Jakarta",
        "TELEGRAM_BOT_TOKEN": "1:abc",
        "TELEGRAM_CHAT_ID": "1",
        "STATE_DIR": str(tmp_path),
        "HEADLESS": "true",
    }.items():
        monkeypatch.setenv(k, v)

    sent: list = []
    monkeypatch.setattr(
        "talenta_bot.notifier.TelegramNotifier.send_text",
        lambda self, text: sent.append(text) or True,
    )
    monkeypatch.setattr(
        "talenta_bot.notifier.TelegramNotifier.send_photo",
        lambda self, caption, photo_path: sent.append(("photo", caption)) or True,
    )

    rc = cli._run_action("clock-in", now=True, skip_window=True, dry_run=False)
    assert rc == 0
    assert len(server.calls) == 1
    assert any("✅" in s for s in sent)
