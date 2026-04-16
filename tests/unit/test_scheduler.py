import pytest
from freezegun import freeze_time

from talenta_bot.scheduler import is_workday, now_in_tz, random_sleep_seconds


@pytest.mark.parametrize(
    "iso,expected",
    [
        ("2026-04-13T08:00:00", True),
        ("2026-04-17T08:00:00", True),
        ("2026-04-18T08:00:00", False),
        ("2026-04-19T08:00:00", False),
    ],
)
def test_is_workday(iso, expected):
    with freeze_time(iso):
        assert is_workday("Asia/Jakarta") is expected


def test_now_in_tz_returns_local():
    with freeze_time("2026-04-16T03:00:00+00:00"):
        dt = now_in_tz("Asia/Jakarta")
        assert dt.hour == 10
        assert dt.tzinfo is not None


def test_random_sleep_bounds():
    samples = [random_sleep_seconds("08:00", "08:15", "Asia/Jakarta") for _ in range(500)]
    assert all(s >= 0 for s in samples)
    assert all(s <= 15 * 60 for s in samples)


def test_random_sleep_uses_remaining_window_if_now_inside_window():
    with freeze_time("2026-04-16T01:10:00+00:00"):
        samples = [
            random_sleep_seconds("08:00", "08:15", "Asia/Jakarta") for _ in range(200)
        ]
        assert all(s <= 5 * 60 for s in samples), max(samples)


def test_random_sleep_zero_if_now_past_window():
    with freeze_time("2026-04-16T02:00:00+00:00"):
        s = random_sleep_seconds("08:00", "08:15", "Asia/Jakarta")
        assert s == 0
