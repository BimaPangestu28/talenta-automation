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


def test_random_sleep_bounded_to_window_when_inside():
    # 08:10 WIB, window 08:00-08:15 → remaining 5 min
    with freeze_time("2026-04-16T01:10:00+00:00"):
        samples = [
            random_sleep_seconds("08:00", "08:15", "Asia/Jakarta") for _ in range(500)
        ]
        assert all(0 <= s <= 5 * 60 for s in samples), max(samples)


def test_random_sleep_waits_until_window_opens_when_called_early():
    # Cron fires at 08:00 WIB but window is 09:00-09:15.
    # Must sleep at least 60 min (until window start) and at most 75 min.
    with freeze_time("2026-04-17T01:00:00+00:00"):  # 08:00 WIB
        samples = [
            random_sleep_seconds("09:00", "09:15", "Asia/Jakarta") for _ in range(500)
        ]
        assert all(60 * 60 <= s <= 75 * 60 for s in samples), (min(samples), max(samples))


def test_random_sleep_within_whole_window_when_called_at_window_start():
    # Exactly at window start: random across the whole window.
    with freeze_time("2026-04-17T02:00:00+00:00"):  # 09:00 WIB
        samples = [
            random_sleep_seconds("09:00", "09:15", "Asia/Jakarta") for _ in range(500)
        ]
        assert all(0 <= s <= 15 * 60 for s in samples), max(samples)


def test_random_sleep_zero_if_now_past_window():
    with freeze_time("2026-04-16T02:00:00+00:00"):  # 09:00 WIB, window 08:00-08:15
        s = random_sleep_seconds("08:00", "08:15", "Asia/Jakarta")
        assert s == 0
