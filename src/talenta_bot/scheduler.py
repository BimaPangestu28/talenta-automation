import random
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo


def now_in_tz(tz: str) -> datetime:
    return datetime.now(tz=ZoneInfo(tz))


def is_workday(tz: str) -> bool:
    return now_in_tz(tz).weekday() < 5


def _parse_hhmm(s: str) -> time:
    h, m = s.split(":")
    return time(hour=int(h), minute=int(m))


def random_sleep_seconds(window_start: str, window_end: str, tz: str) -> int:
    """Seconds to sleep so that the action lands at a uniform-random point
    within [window_start, window_end].

    - If called before ``window_start``: sleep includes the wait until the
      window opens PLUS a random offset within the window.
    - If called during the window: random offset within the remaining window.
    - If called after ``window_end``: 0 (act immediately — caller decides
      whether to still proceed; cron backstop covers this).
    """
    now = now_in_tz(tz)
    today = now.date()
    start_dt = datetime.combine(today, _parse_hhmm(window_start), tzinfo=ZoneInfo(tz))
    end_dt = datetime.combine(today, _parse_hhmm(window_end), tzinfo=ZoneInfo(tz))

    if now >= end_dt:
        return 0
    effective_start = max(now, start_dt)
    span_seconds = int((end_dt - effective_start).total_seconds())
    offset_within_window = random.randint(0, max(span_seconds, 0))
    target = effective_start + timedelta(seconds=offset_within_window)
    return int((target - now).total_seconds())
