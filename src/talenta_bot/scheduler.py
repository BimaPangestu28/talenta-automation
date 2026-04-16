import random
from datetime import datetime, time
from zoneinfo import ZoneInfo


def now_in_tz(tz: str) -> datetime:
    return datetime.now(tz=ZoneInfo(tz))


def is_workday(tz: str) -> bool:
    return now_in_tz(tz).weekday() < 5


def _parse_hhmm(s: str) -> time:
    h, m = s.split(":")
    return time(hour=int(h), minute=int(m))


def random_sleep_seconds(window_start: str, window_end: str, tz: str) -> int:
    now = now_in_tz(tz)
    today = now.date()
    start_dt = datetime.combine(today, _parse_hhmm(window_start), tzinfo=ZoneInfo(tz))
    end_dt = datetime.combine(today, _parse_hhmm(window_end), tzinfo=ZoneInfo(tz))

    if now >= end_dt:
        return 0
    effective_start = max(now, start_dt)
    span = int((end_dt - effective_start).total_seconds())
    return random.randint(0, max(span, 0))
