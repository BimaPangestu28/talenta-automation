import pytest
from pydantic import ValidationError

from talenta_bot.config import Settings

VALID_ENV = {
    "MEKARI_EMAIL": "u@example.com",
    "MEKARI_PASSWORD": "pw",
    "OFFICE_LAT": "-6.2",
    "OFFICE_LONG": "106.8",
    "GEO_JITTER_METERS": "5",
    "CLOCK_IN_WINDOW_START": "08:00",
    "CLOCK_IN_WINDOW_END": "08:15",
    "CLOCK_OUT_WINDOW_START": "17:05",
    "CLOCK_OUT_WINDOW_END": "17:30",
    "TIMEZONE": "Asia/Jakarta",
    "TELEGRAM_BOT_TOKEN": "123456:ABC_def-XYZ",
    "TELEGRAM_CHAT_ID": "123",
    "STATE_DIR": "/tmp/state",
    "HEADLESS": "true",
}


def test_valid_env_parses(monkeypatch):
    for k, v in VALID_ENV.items():
        monkeypatch.setenv(k, v)
    s = Settings()
    assert s.mekari_email == "u@example.com"
    assert s.office_lat == -6.2
    assert s.clock_in_window_start == "08:00"
    assert s.headless is True


@pytest.mark.parametrize(
    "key,bad,msg",
    [
        ("MEKARI_EMAIL", "noat", "missing @"),
        ("OFFICE_LAT", "40.0", "less than or equal"),
        ("OFFICE_LONG", "-70.0", "greater than or equal"),
        ("CLOCK_IN_WINDOW_START", "25:00", "not HH:MM"),
        ("TELEGRAM_BOT_TOKEN", "bad-token", "telegram token"),
        ("TIMEZONE", "Mars/Olympus", "invalid timezone"),
    ],
)
def test_bad_env_rejected(monkeypatch, key, bad, msg):
    env = VALID_ENV.copy()
    env[key] = bad
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    with pytest.raises(ValidationError) as exc:
        Settings()
    assert msg in str(exc.value)


def test_window_end_must_follow_start(monkeypatch):
    env = VALID_ENV.copy()
    env["CLOCK_IN_WINDOW_END"] = "07:00"
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    with pytest.raises(ValidationError) as exc:
        Settings()
    assert "end" in str(exc.value) and "must be > start" in str(exc.value)
