# Talenta Automation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a VPS-deployable Docker container that automatically clocks in and clocks out on Talenta (Mekari HR platform) on weekdays, with randomised timing, persisted browser session, idempotency, and Telegram notifications.

**Architecture:** Python + Playwright (Chromium headless) inside a single Docker container. `supercronic` triggers four cron jobs per day (primary + backstop for clock-in and clock-out). Each run: load persisted `storage_state.json`, relogin if expired, verify not-already-done, click the action button with geolocation override, notify via Telegram. Config via `.env`; state via mounted volume.

**Tech Stack:** Python 3.11, Playwright ≥1.49, pydantic-settings, httpx, typer, pytest, freezegun, aiohttp (mock server), Docker, docker compose, supercronic.

**Spec:** `docs/superpowers/specs/2026-04-16-talenta-automation-design.md`

---

## File Map

| File | Responsibility |
|---|---|
| `pyproject.toml` | Package metadata, dependencies, pytest/ruff config, script entrypoint |
| `.env.example` | Template for all required environment variables |
| `.gitignore` | Exclude `state/`, `.env`, `__pycache__`, build artefacts |
| `.dockerignore` | Exclude `.git`, `.env`, `state/`, tests from image |
| `src/talenta_bot/__init__.py` | Package marker with version string |
| `src/talenta_bot/__main__.py` | Allow `python -m talenta_bot` by delegating to `cli.app` |
| `src/talenta_bot/config.py` | `Settings` class (pydantic-settings) with validators |
| `src/talenta_bot/scheduler.py` | `is_workday()`, `random_sleep_seconds()`, `now_in_tz()` helpers |
| `src/talenta_bot/notifier.py` | `TelegramNotifier` — `info()`, `success()`, `warning()`, `critical()`, `send_screenshot()` |
| `src/talenta_bot/selectors.py` | All Mekari/Talenta UI selectors as constants (captured live in Task 5) |
| `src/talenta_bot/session.py` | `jittered_coords()`, `playwright_page()` context manager, `login_flow()` |
| `src/talenta_bot/attendance.py` | `already_clocked_in_today()`, `already_clocked_out_today()`, `click_clock_in()`, `click_clock_out()` |
| `src/talenta_bot/errors.py` | Exception taxonomy classes (`LoginFailed`, `TalentaDown`, `SelectorNotFound`, `ClockActionFailed`) |
| `src/talenta_bot/cli.py` | Typer app with `login`, `clock-in`, `clock-out` commands; orchestration + error handling |
| `tests/unit/test_config.py` | Validate env parsing |
| `tests/unit/test_scheduler.py` | is_workday, random_sleep_seconds |
| `tests/unit/test_notifier.py` | Message building + mock Telegram client |
| `tests/unit/test_session.py` | jittered_coords math |
| `tests/integration/test_clock_in_happy_path.py` | Full CLI run against aiohttp mock server |
| `tests/integration/conftest.py` | Mock server fixture |
| `Dockerfile` | Playwright base image + supercronic + app |
| `docker-compose.yml` | Service definition with env_file, volumes, logging rotation |
| `crontab` | supercronic schedule (4 entries: primary + backstop × clock-in/out) |
| `README.md` | Setup instructions + operational commands |
| `docs/SMOKE.md` | Manual post-deploy smoke checklist |

---

## Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `src/talenta_bot/__init__.py`
- Create: `src/talenta_bot/__main__.py`
- Create: `tests/__init__.py`
- Create: `tests/unit/__init__.py`
- Create: `tests/integration/__init__.py`

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[project]
name = "talenta-bot"
version = "0.1.0"
description = "Automated clock-in/out for Talenta (Mekari HR)"
requires-python = ">=3.11"
dependencies = [
    "playwright>=1.49,<2.0",
    "pydantic>=2.6,<3.0",
    "pydantic-settings>=2.2,<3.0",
    "httpx>=0.27,<1.0",
    "typer>=0.12,<1.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0,<9.0",
    "pytest-asyncio>=0.23,<1.0",
    "freezegun>=1.4,<2.0",
    "aiohttp>=3.9,<4.0",
    "ruff>=0.5,<1.0",
]

[project.scripts]
talenta-bot = "talenta_bot.cli:app"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/talenta_bot"]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "UP", "B", "SIM"]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

- [ ] **Step 2: Write `.gitignore`**

```gitignore
__pycache__/
*.py[cod]
*.egg-info/
.pytest_cache/
.ruff_cache/
build/
dist/
.venv/
venv/

# Runtime state — never commit
state/
.env

# IDE
.vscode/
.idea/
*.swp
```

- [ ] **Step 3: Write `.env.example`**

```env
# Mekari credentials
MEKARI_EMAIL=you@example.com
MEKARI_PASSWORD=your-password

# Geolocation (decimal degrees) — Jakarta placeholder
OFFICE_LAT=-6.200000
OFFICE_LONG=106.816666
GEO_JITTER_METERS=5

# Schedule windows (local time HH:MM)
CLOCK_IN_WINDOW_START=08:00
CLOCK_IN_WINDOW_END=08:15
CLOCK_OUT_WINDOW_START=17:05
CLOCK_OUT_WINDOW_END=17:30
TIMEZONE=Asia/Jakarta

# Telegram bot
TELEGRAM_BOT_TOKEN=123456:replace-me
TELEGRAM_CHAT_ID=12345678

# Runtime
STATE_DIR=/app/state
HEADLESS=true
```

- [ ] **Step 4: Write `src/talenta_bot/__init__.py`**

```python
__version__ = "0.1.0"
```

- [ ] **Step 5: Write `src/talenta_bot/__main__.py`**

```python
from talenta_bot.cli import app

if __name__ == "__main__":
    app()
```

- [ ] **Step 6: Write empty package markers**

```bash
touch tests/__init__.py tests/unit/__init__.py tests/integration/__init__.py
```

- [ ] **Step 7: Install in editable mode and verify**

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python -c "import talenta_bot; print(talenta_bot.__version__)"
```

Expected output: `0.1.0`

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml .gitignore .env.example src/ tests/
git commit -m "chore: scaffold talenta-bot package"
```

---

## Task 2: Config Module (TDD)

**Files:**
- Create: `src/talenta_bot/config.py`
- Test: `tests/unit/test_config.py`

- [ ] **Step 1: Write failing test for valid config**

```python
# tests/unit/test_config.py
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/unit/test_config.py::test_valid_env_parses -v
```

Expected: `ImportError: cannot import name 'Settings' from 'talenta_bot.config'` (module doesn't exist).

- [ ] **Step 3: Write minimal `config.py`**

```python
# src/talenta_bot/config.py
import re
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
TELEGRAM_TOKEN_RE = re.compile(r"^\d+:[\w-]+$")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mekari_email: str = Field(min_length=3)
    mekari_password: str = Field(min_length=1)

    office_lat: float = Field(ge=-11.5, le=6.5)
    office_long: float = Field(ge=94.5, le=141.5)
    geo_jitter_meters: float = Field(default=5.0, ge=0)

    clock_in_window_start: str
    clock_in_window_end: str
    clock_out_window_start: str
    clock_out_window_end: str
    timezone: str = "Asia/Jakarta"

    telegram_bot_token: str
    telegram_chat_id: str

    state_dir: Path = Path("/app/state")
    headless: bool = True

    @field_validator("mekari_email")
    @classmethod
    def _email_has_at(cls, v: str) -> str:
        if "@" not in v:
            raise ValueError("email missing @")
        return v

    @field_validator(
        "clock_in_window_start",
        "clock_in_window_end",
        "clock_out_window_start",
        "clock_out_window_end",
    )
    @classmethod
    def _hhmm(cls, v: str) -> str:
        if not TIME_RE.match(v):
            raise ValueError(f"not HH:MM: {v!r}")
        return v

    @field_validator("telegram_bot_token")
    @classmethod
    def _token_shape(cls, v: str) -> str:
        if not TELEGRAM_TOKEN_RE.match(v):
            raise ValueError("telegram token must match <digits>:<alnum/-/_>")
        return v

    @field_validator("timezone")
    @classmethod
    def _tz_resolvable(cls, v: str) -> str:
        try:
            ZoneInfo(v)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"invalid timezone {v!r}") from exc
        return v

    @model_validator(mode="after")
    def _windows_in_order(self) -> "Settings":
        pairs = [
            ("clock_in", self.clock_in_window_start, self.clock_in_window_end),
            ("clock_out", self.clock_out_window_start, self.clock_out_window_end),
        ]
        for name, start, end in pairs:
            if end <= start:
                raise ValueError(f"{name} window: end {end!r} must be > start {start!r}")
        return self
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/unit/test_config.py::test_valid_env_parses -v
```

Expected: PASS.

- [ ] **Step 5: Add failing tests for rejection cases**

```python
# Append to tests/unit/test_config.py

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
    env["CLOCK_IN_WINDOW_END"] = "07:00"  # before start
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    with pytest.raises(ValidationError) as exc:
        Settings()
    assert "end" in str(exc.value) and "must be > start" in str(exc.value)
```

- [ ] **Step 6: Run full config test suite**

```bash
pytest tests/unit/test_config.py -v
```

Expected: all tests PASS.

- [ ] **Step 7: Commit**

```bash
git add src/talenta_bot/config.py tests/unit/test_config.py
git commit -m "feat(config): pydantic Settings with env validation"
```

---

## Task 3: Scheduler Module (TDD)

**Files:**
- Create: `src/talenta_bot/scheduler.py`
- Test: `tests/unit/test_scheduler.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_scheduler.py
from datetime import datetime

import pytest
from freezegun import freeze_time

from talenta_bot.scheduler import is_workday, now_in_tz, random_sleep_seconds


@pytest.mark.parametrize(
    "iso,expected",
    [
        ("2026-04-13T08:00:00", True),   # Monday
        ("2026-04-17T08:00:00", True),   # Friday
        ("2026-04-18T08:00:00", False),  # Saturday
        ("2026-04-19T08:00:00", False),  # Sunday
    ],
)
def test_is_workday(iso, expected):
    with freeze_time(iso):
        assert is_workday("Asia/Jakarta") is expected


def test_now_in_tz_returns_local():
    with freeze_time("2026-04-16T03:00:00+00:00"):  # 10:00 WIB
        dt = now_in_tz("Asia/Jakarta")
        assert dt.hour == 10
        assert dt.tzinfo is not None


def test_random_sleep_bounds():
    samples = [random_sleep_seconds("08:00", "08:15", "Asia/Jakarta") for _ in range(500)]
    assert all(s >= 0 for s in samples)
    assert all(s <= 15 * 60 for s in samples)


def test_random_sleep_uses_remaining_window_if_now_inside_window():
    # At 08:10 WIB with window 08:00-08:15, must sleep ≤5 minutes
    with freeze_time("2026-04-16T01:10:00+00:00"):  # 08:10 WIB
        samples = [
            random_sleep_seconds("08:00", "08:15", "Asia/Jakarta") for _ in range(200)
        ]
        assert all(s <= 5 * 60 for s in samples), max(samples)


def test_random_sleep_zero_if_now_past_window():
    with freeze_time("2026-04-16T02:00:00+00:00"):  # 09:00 WIB
        s = random_sleep_seconds("08:00", "08:15", "Asia/Jakarta")
        assert s == 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/unit/test_scheduler.py -v
```

Expected: `ImportError: cannot import name 'is_workday' from 'talenta_bot.scheduler'`.

- [ ] **Step 3: Implement scheduler**

```python
# src/talenta_bot/scheduler.py
import random
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo


def now_in_tz(tz: str) -> datetime:
    return datetime.now(tz=ZoneInfo(tz))


def is_workday(tz: str) -> bool:
    return now_in_tz(tz).weekday() < 5  # Mon=0, Sun=6


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


def sleep_until_window_offset(window_start: str, window_end: str, tz: str) -> int:
    """Convenience — returns seconds the caller should sleep; 0 means act now."""
    return random_sleep_seconds(window_start, window_end, tz)
```

- [ ] **Step 4: Run tests to verify pass**

```bash
pytest tests/unit/test_scheduler.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/talenta_bot/scheduler.py tests/unit/test_scheduler.py
git commit -m "feat(scheduler): is_workday + random_sleep within window"
```

---

## Task 4: Errors Module

**Files:**
- Create: `src/talenta_bot/errors.py`

- [ ] **Step 1: Write exception classes**

```python
# src/talenta_bot/errors.py
"""Exception taxonomy — each class maps to a Telegram notification category."""


class TalentaBotError(Exception):
    """Base for all app errors that should reach the notifier."""

    category: str = "Unknown"


class ConfigError(TalentaBotError):
    category = "ConfigError"


class LoginFailed(TalentaBotError):
    category = "LoginFailed"


class TalentaDown(TalentaBotError):
    category = "TalentaDown"


class SelectorNotFound(TalentaBotError):
    category = "SelectorNotFound"


class ClockActionFailed(TalentaBotError):
    category = "ClockActionFailed"


class SkippedAlreadyClocked(TalentaBotError):
    """Not a failure — raised to short-circuit flow, caught at CLI level."""

    category = "SkippedAlreadyClocked"
```

- [ ] **Step 2: Commit**

```bash
git add src/talenta_bot/errors.py
git commit -m "feat(errors): exception taxonomy"
```

---

## Task 5: Capture Mekari / Talenta Selectors (Research)

**Files:**
- Create: `src/talenta_bot/selectors.py`

**Why this task:** We cannot guess exact selectors for Mekari SSO + Talenta dashboard without inspecting the live site. This task produces a file of verified constants that later tasks reference.

**Prerequisite:** Real Mekari credentials placed in a local `.env` for a one-time browser session.

- [ ] **Step 1: Install Chromium for Playwright**

```bash
playwright install chromium
```

- [ ] **Step 2: Launch a visible browser session and capture selectors**

```bash
playwright open "https://account.mekari.com/users/sign_in?client_id=TAL-73645&return_to=L2F1dGg_Y2xpZW50X2lkPVRBTC03MzY0NSZyZXNwb25zZV90eXBlPWNvZGUmc2NvcGU9c3NvOnByb2ZpbGU%3D"
```

Using DevTools, log in and capture the CSS/role/text selectors for:

1. **Email input** on SSO page (likely `input[name='user[email]']` or `#user_email`).
2. **Password input** (likely `input[name='user[password]']` or `#user_password`).
3. **Submit button(s)** — verify whether SSO is one-step (email+password together) or two-step.
4. **Post-login URL pattern** (e.g. `https://hr.talenta.co/live-attendance`).
5. **Clock In button** on Live Attendance page (record its accessible role + name, and a CSS fallback).
6. **Clock Out button** (record both).
7. **Today's attendance card** — the element that shows an entry exists and includes today's clock-in time.
8. **Success toast / modal** after a successful click.
9. **Login error banner** shown on bad credentials.

- [ ] **Step 3: Write `selectors.py` with captured values**

```python
# src/talenta_bot/selectors.py
"""Captured selectors for Mekari SSO and Talenta dashboard.

Update when upstream UI changes. Each constant is either:
- a CSS selector string (preferred for stable id/name attributes), or
- a Playwright ``role=`` / ``text=`` locator string.
"""

# --- Mekari SSO (account.mekari.com) ---
SSO_LOGIN_URL = (
    "https://account.mekari.com/users/sign_in"
    "?client_id=TAL-73645&return_to=L2F1dGg_Y2xpZW50X2lkPVRBTC03MzY0NSZyZXNwb25zZV90eXBlPWNvZGUmc2NvcGU9c3NvOnByb2ZpbGU%3D"
)
SSO_EMAIL_INPUT = "input[name='user[email]']"
SSO_PASSWORD_INPUT = "input[name='user[password]']"
SSO_SUBMIT_BUTTON = "button[type='submit']"
SSO_ERROR_BANNER = ".alert-danger, [role='alert']"
SSO_IS_TWO_STEP = False  # True if email first, password on next screen

# --- Talenta dashboard ---
TALENTA_BASE_URL = "https://hr.talenta.co"
LIVE_ATTENDANCE_URL = "https://hr.talenta.co/live-attendance"
DASHBOARD_URL_PATTERN = "**/hr.talenta.co/**"

CLOCK_IN_BUTTON = "button:has-text('Clock In')"
CLOCK_OUT_BUTTON = "button:has-text('Clock Out')"

TODAYS_ENTRY_CARD = "[data-testid='today-attendance-card']"
CLOCK_IN_TIME_DISPLAY = "[data-testid='clock-in-time']"
CLOCK_OUT_TIME_DISPLAY = "[data-testid='clock-out-time']"

ACTION_SUCCESS_TOAST = ".toast-success, [role='status']:has-text('success')"
ACTION_ERROR_TOAST = ".toast-error, [role='alert']"
```

> **Note to engineer:** The values above are best-guess defaults. Replace each one with what you actually saw in DevTools during Step 2. If `data-testid` attributes don't exist, fall back to visible text (`:has-text('...')`) or stable CSS class names. Record `SSO_IS_TWO_STEP` correctly.

- [ ] **Step 4: Commit**

```bash
git add src/talenta_bot/selectors.py
git commit -m "feat(selectors): capture Mekari SSO + Talenta dashboard selectors"
```

---

## Task 6: Notifier — Message Building (TDD)

**Files:**
- Create: `src/talenta_bot/notifier.py`
- Test: `tests/unit/test_notifier.py`

- [ ] **Step 1: Write failing tests for message composition**

```python
# tests/unit/test_notifier.py
from datetime import datetime
from zoneinfo import ZoneInfo

from talenta_bot.notifier import build_message


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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/unit/test_notifier.py -v
```

Expected: ImportError — notifier doesn't exist.

- [ ] **Step 3: Implement `build_message` and the sending skeleton**

```python
# src/talenta_bot/notifier.py
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Literal

import httpx

logger = logging.getLogger(__name__)

Kind = Literal["success", "info", "warning", "critical"]

_PREFIX = {
    "success": "✅",
    "info": "ℹ️",
    "warning": "⚠️",
    "critical": "🚨",
}


def build_message(
    *,
    kind: Kind,
    action: str,
    ts: datetime,
    note: str | None = None,
    category: str | None = None,
    reason: str | None = None,
) -> str:
    prefix = _PREFIX[kind]
    hhmm = ts.strftime("%H:%M")
    tz = ts.strftime("%Z") or "WIB"

    if kind == "success":
        return f"{prefix} {action} {hhmm} {tz} — Talenta OK"
    if kind == "info":
        return f"{prefix} {action} — skipped, {note or ''}".rstrip(", ")
    # warning or critical
    tail = f": {reason}" if reason else ""
    return f"{prefix} {action} {kind.upper()} — {category or 'Unknown'}{tail}"


class TelegramNotifier:
    """Thin wrapper around Telegram Bot API. Failures are logged, not raised."""

    def __init__(self, bot_token: str, chat_id: str, timeout: float = 10.0):
        self._base = f"https://api.telegram.org/bot{bot_token}"
        self._chat_id = chat_id
        self._timeout = timeout

    def send_text(self, text: str) -> bool:
        try:
            r = httpx.post(
                f"{self._base}/sendMessage",
                data={"chat_id": self._chat_id, "text": text},
                timeout=self._timeout,
            )
            r.raise_for_status()
            return True
        except httpx.HTTPError:
            logger.exception("telegram send_text failed")
            return False

    def send_photo(self, caption: str, photo_path: Path) -> bool:
        try:
            with photo_path.open("rb") as fh:
                r = httpx.post(
                    f"{self._base}/sendPhoto",
                    data={"chat_id": self._chat_id, "caption": caption},
                    files={"photo": fh},
                    timeout=self._timeout,
                )
            r.raise_for_status()
            return True
        except (httpx.HTTPError, OSError):
            logger.exception("telegram send_photo failed")
            return False
```

- [ ] **Step 4: Add test for `TelegramNotifier.send_text` using monkeypatched httpx**

```python
# Append to tests/unit/test_notifier.py
import httpx

from talenta_bot.notifier import TelegramNotifier


def test_send_text_calls_bot_api(monkeypatch):
    captured: dict = {}

    def fake_post(url, data=None, timeout=None, **_kwargs):
        captured["url"] = url
        captured["data"] = data
        return httpx.Response(200, json={"ok": True})

    monkeypatch.setattr(httpx, "post", fake_post)

    ok = TelegramNotifier("123:abc", "42").send_text("hi")
    assert ok is True
    assert captured["url"] == "https://api.telegram.org/bot123:abc/sendMessage"
    assert captured["data"] == {"chat_id": "42", "text": "hi"}


def test_send_text_returns_false_on_http_error(monkeypatch):
    def fake_post(url, data=None, timeout=None, **_kwargs):
        return httpx.Response(500)

    monkeypatch.setattr(httpx, "post", fake_post)
    assert TelegramNotifier("123:abc", "42").send_text("hi") is False
```

- [ ] **Step 5: Run full notifier test file**

```bash
pytest tests/unit/test_notifier.py -v
```

Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add src/talenta_bot/notifier.py tests/unit/test_notifier.py
git commit -m "feat(notifier): message composer + Telegram wrapper"
```

---

## Task 7: Session — Geolocation Helper (TDD)

**Files:**
- Create: `src/talenta_bot/session.py` (partial — only `jittered_coords` for now)
- Test: `tests/unit/test_session.py`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/test_session.py
import math

from talenta_bot.session import jittered_coords


def test_jittered_coords_within_radius():
    base_lat, base_long = -6.2, 106.8
    max_m = 5.0
    for _ in range(500):
        lat, lon = jittered_coords(base_lat, base_long, max_m)
        # Approx distance
        d_lat = (lat - base_lat) * 111_000
        d_lon = (lon - base_long) * 111_000 * math.cos(math.radians(base_lat))
        dist = math.hypot(d_lat, d_lon)
        assert dist <= max_m + 0.01, dist


def test_jittered_coords_zero_is_exact():
    lat, lon = jittered_coords(-6.2, 106.8, 0)
    assert (lat, lon) == (-6.2, 106.8)
```

- [ ] **Step 2: Run to verify it fails**

```bash
pytest tests/unit/test_session.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement the helper**

```python
# src/talenta_bot/session.py
from __future__ import annotations

import math
import random


def jittered_coords(lat: float, lon: float, max_meters: float) -> tuple[float, float]:
    """Return (lat, lon) offset by a uniform-random vector of length ≤ max_meters."""
    if max_meters <= 0:
        return lat, lon
    # Uniform point in disk
    theta = random.uniform(0, 2 * math.pi)
    r = max_meters * math.sqrt(random.random())
    d_lat = (r * math.cos(theta)) / 111_000
    d_lon = (r * math.sin(theta)) / (111_000 * math.cos(math.radians(lat)))
    return lat + d_lat, lon + d_lon
```

- [ ] **Step 4: Run and verify pass**

```bash
pytest tests/unit/test_session.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/talenta_bot/session.py tests/unit/test_session.py
git commit -m "feat(session): jittered_coords helper"
```

---

## Task 8: Session — Browser Context + Login Flow

**Files:**
- Modify: `src/talenta_bot/session.py` (append)

- [ ] **Step 1: Extend `session.py` with the Playwright context manager and login flow**

```python
# Append to src/talenta_bot/session.py

import logging
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator

from playwright.sync_api import (
    BrowserContext,
    Page,
    Playwright,
    TimeoutError as PWTimeoutError,
    sync_playwright,
)

from talenta_bot.config import Settings
from talenta_bot.errors import LoginFailed, TalentaDown
from talenta_bot.selectors import (
    DASHBOARD_URL_PATTERN,
    SSO_EMAIL_INPUT,
    SSO_ERROR_BANNER,
    SSO_IS_TWO_STEP,
    SSO_LOGIN_URL,
    SSO_PASSWORD_INPUT,
    SSO_SUBMIT_BUTTON,
    TALENTA_BASE_URL,
)

logger = logging.getLogger(__name__)

STORAGE_STATE_FILENAME = "storage_state.json"
STATE_TTL = timedelta(days=7)
DEFAULT_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)


def _storage_state_path(state_dir: Path) -> Path:
    return state_dir / STORAGE_STATE_FILENAME


def _is_state_fresh(path: Path) -> bool:
    if not path.exists():
        return False
    age = datetime.now(tz=timezone.utc) - datetime.fromtimestamp(
        path.stat().st_mtime, tz=timezone.utc
    )
    return age < STATE_TTL


@contextmanager
def playwright_page(settings: Settings) -> Iterator[tuple[Page, BrowserContext]]:
    """Launch Chromium, yield (page, context). Save storage_state on successful exit."""
    state_path = _storage_state_path(settings.state_dir)
    settings.state_dir.mkdir(parents=True, exist_ok=True)

    lat, lon = jittered_coords(
        settings.office_lat, settings.office_long, settings.geo_jitter_meters
    )

    context_kwargs = {
        "geolocation": {"latitude": lat, "longitude": lon, "accuracy": 20},
        "permissions": ["geolocation"],
        "locale": "id-ID",
        "timezone_id": settings.timezone,
        "viewport": {"width": 1280, "height": 800},
        "user_agent": DEFAULT_UA,
    }
    if _is_state_fresh(state_path):
        context_kwargs["storage_state"] = str(state_path)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=settings.headless)
        context = browser.new_context(**context_kwargs)
        page = context.new_page()
        try:
            _ensure_logged_in(page, settings)
            yield page, context
            context.storage_state(path=str(state_path))
        finally:
            context.close()
            browser.close()


def _ensure_logged_in(page: Page, settings: Settings) -> None:
    """Goto dashboard; if redirected to SSO, run login flow and persist state."""
    try:
        page.goto(TALENTA_BASE_URL, timeout=20_000, wait_until="domcontentloaded")
    except PWTimeoutError as exc:
        raise TalentaDown(f"goto {TALENTA_BASE_URL} timed out") from exc

    if _looks_like_login_page(page):
        _login_flow(page, settings.mekari_email, settings.mekari_password)


def _looks_like_login_page(page: Page) -> bool:
    url = page.url
    return "account.mekari.com" in url or "/users/sign_in" in url


def _login_flow(page: Page, email: str, password: str) -> None:
    logger.info("running login flow")
    try:
        # If already on login, just fill; otherwise navigate.
        if "account.mekari.com" not in page.url:
            page.goto(SSO_LOGIN_URL, timeout=20_000)

        page.wait_for_selector(SSO_EMAIL_INPUT, timeout=10_000)
        page.fill(SSO_EMAIL_INPUT, email)

        if SSO_IS_TWO_STEP:
            page.click(SSO_SUBMIT_BUTTON)
            page.wait_for_selector(SSO_PASSWORD_INPUT, timeout=10_000)

        page.fill(SSO_PASSWORD_INPUT, password)
        page.click(SSO_SUBMIT_BUTTON)

        # Either we land on hr.talenta.co (success) or see an error banner (fail).
        try:
            page.wait_for_url(DASHBOARD_URL_PATTERN, timeout=30_000)
        except PWTimeoutError as exc:
            err_text = _safe_text(page, SSO_ERROR_BANNER)
            raise LoginFailed(err_text or "did not reach dashboard after login") from exc
    except PWTimeoutError as exc:
        raise LoginFailed(f"login step timed out: {exc}") from exc


def _safe_text(page: Page, selector: str, timeout: float = 1.0) -> str | None:
    try:
        el = page.wait_for_selector(selector, timeout=int(timeout * 1000))
        return el.inner_text() if el else None
    except PWTimeoutError:
        return None
```

- [ ] **Step 2: Sanity-check import**

```bash
python -c "from talenta_bot.session import playwright_page; print('ok')"
```

Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add src/talenta_bot/session.py
git commit -m "feat(session): browser context manager + SSO login flow"
```

---

## Task 9: Attendance — Status Checks and Click Actions

**Files:**
- Create: `src/talenta_bot/attendance.py`

- [ ] **Step 1: Implement attendance operations**

```python
# src/talenta_bot/attendance.py
from __future__ import annotations

import logging

from playwright.sync_api import Page, TimeoutError as PWTimeoutError

from talenta_bot.errors import ClockActionFailed, SelectorNotFound
from talenta_bot.selectors import (
    ACTION_ERROR_TOAST,
    ACTION_SUCCESS_TOAST,
    CLOCK_IN_BUTTON,
    CLOCK_IN_TIME_DISPLAY,
    CLOCK_OUT_BUTTON,
    CLOCK_OUT_TIME_DISPLAY,
    LIVE_ATTENDANCE_URL,
)

logger = logging.getLogger(__name__)

WAIT_SELECTOR_MS = 15_000
WAIT_CONFIRM_MS = 15_000


def _goto_live_attendance(page: Page) -> None:
    page.goto(LIVE_ATTENDANCE_URL, wait_until="domcontentloaded", timeout=20_000)


def _time_text(page: Page, selector: str) -> str | None:
    try:
        el = page.wait_for_selector(selector, timeout=2_000)
        if not el:
            return None
        text = el.inner_text().strip()
        return text or None
    except PWTimeoutError:
        return None


def already_clocked_in_today(page: Page) -> str | None:
    """Return the clock-in time (HH:MM) if already recorded, else None."""
    _goto_live_attendance(page)
    return _time_text(page, CLOCK_IN_TIME_DISPLAY)


def already_clocked_out_today(page: Page) -> str | None:
    _goto_live_attendance(page)
    return _time_text(page, CLOCK_OUT_TIME_DISPLAY)


def _click_and_confirm(page: Page, button_selector: str, action_name: str) -> None:
    try:
        page.wait_for_selector(button_selector, timeout=WAIT_SELECTOR_MS)
    except PWTimeoutError as exc:
        raise SelectorNotFound(
            f"{action_name}: button {button_selector!r} not found"
        ) from exc

    page.click(button_selector)

    # Confirm via success toast OR updated time display
    try:
        page.wait_for_selector(
            f"{ACTION_SUCCESS_TOAST}, {CLOCK_IN_TIME_DISPLAY}, {CLOCK_OUT_TIME_DISPLAY}",
            timeout=WAIT_CONFIRM_MS,
        )
    except PWTimeoutError as exc:
        err = _time_text(page, ACTION_ERROR_TOAST) or "no confirmation within 15s"
        raise ClockActionFailed(f"{action_name}: {err}") from exc


def click_clock_in(page: Page) -> None:
    logger.info("clicking Clock In")
    _click_and_confirm(page, CLOCK_IN_BUTTON, "Clock In")


def click_clock_out(page: Page) -> None:
    logger.info("clicking Clock Out")
    _click_and_confirm(page, CLOCK_OUT_BUTTON, "Clock Out")
```

- [ ] **Step 2: Sanity import check**

```bash
python -c "from talenta_bot.attendance import click_clock_in, already_clocked_in_today; print('ok')"
```

- [ ] **Step 3: Commit**

```bash
git add src/talenta_bot/attendance.py
git commit -m "feat(attendance): clock in/out + idempotency checks"
```

---

## Task 10: CLI — Orchestration + Error Taxonomy

**Files:**
- Create: `src/talenta_bot/cli.py`

- [ ] **Step 1: Implement the typer app**

```python
# src/talenta_bot/cli.py
from __future__ import annotations

import logging
import sys
import time
from datetime import datetime
from pathlib import Path

import typer
from playwright.sync_api import TimeoutError as PWTimeoutError
from pydantic import ValidationError

from talenta_bot import attendance as att
from talenta_bot.config import Settings
from talenta_bot.errors import (
    ClockActionFailed,
    ConfigError,
    LoginFailed,
    SelectorNotFound,
    SkippedAlreadyClocked,
    TalentaBotError,
    TalentaDown,
)
from talenta_bot.notifier import TelegramNotifier, build_message
from talenta_bot.scheduler import is_workday, now_in_tz, random_sleep_seconds
from talenta_bot.session import playwright_page

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("talenta_bot")

app = typer.Typer(help="Talenta auto clock-in/out bot.", no_args_is_help=True)

WINDOWS = {
    "clock-in": ("clock_in_window_start", "clock_in_window_end"),
    "clock-out": ("clock_out_window_start", "clock_out_window_end"),
}


def _load_settings() -> Settings:
    try:
        return Settings()
    except ValidationError as exc:
        raise ConfigError(str(exc)) from exc


def _screenshot(page, state_dir: Path, category: str) -> Path | None:
    try:
        state_dir.mkdir(parents=True, exist_ok=True)
        path = state_dir / f"err-{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}-{category}.png"
        page.screenshot(path=str(path), full_page=True)
        return path
    except Exception:
        logger.exception("failed to capture screenshot")
        return None


def _prune_old_screenshots(state_dir: Path, keep_days: int = 7) -> None:
    if not state_dir.exists():
        return
    cutoff = time.time() - keep_days * 86400
    for p in state_dir.glob("err-*.png"):
        if p.stat().st_mtime < cutoff:
            p.unlink(missing_ok=True)


def _run_action(
    action: str,
    *,
    now: bool,
    skip_window: bool,
    dry_run: bool,
) -> int:
    try:
        settings = _load_settings()
    except ConfigError as exc:
        print(f"ConfigError: {exc}", file=sys.stderr)
        return 2

    notifier = TelegramNotifier(settings.telegram_bot_token, settings.telegram_chat_id)
    _prune_old_screenshots(settings.state_dir)

    if not skip_window and not is_workday(settings.timezone):
        logger.info("weekend — exit silently")
        return 0

    if not now:
        start, end = WINDOWS[action]
        delay = random_sleep_seconds(
            getattr(settings, start), getattr(settings, end), settings.timezone
        )
        logger.info("sleeping %ds before %s", delay, action)
        time.sleep(delay)

    display_name = "Clock In" if action == "clock-in" else "Clock Out"
    already_fn = att.already_clocked_in_today if action == "clock-in" else att.already_clocked_out_today
    click_fn = att.click_clock_in if action == "clock-in" else att.click_clock_out

    ts_now = now_in_tz(settings.timezone)

    try:
        with playwright_page(settings) as (page, _ctx):
            existing = already_fn(page)
            if existing:
                msg = build_message(
                    kind="info",
                    action=display_name,
                    ts=ts_now,
                    note=f"tercatat {existing} (manual)",
                )
                notifier.send_text(msg)
                return 0

            if dry_run:
                logger.info("dry-run: would click %s button", display_name)
                return 0

            click_fn(page)
            msg = build_message(kind="success", action=display_name, ts=now_in_tz(settings.timezone))
            notifier.send_text(msg)
            return 0

    except LoginFailed as exc:
        return _notify_error("critical", display_name, settings, notifier, "LoginFailed", exc, page_for_shot=None)
    except TalentaDown as exc:
        return _notify_error("warning", display_name, settings, notifier, "TalentaDown", exc, page_for_shot=None)
    except SelectorNotFound as exc:
        return _notify_error("critical", display_name, settings, notifier, "SelectorNotFound", exc, page_for_shot=None)
    except ClockActionFailed as exc:
        return _notify_error("warning", display_name, settings, notifier, "ClockActionFailed", exc, page_for_shot=None)
    except (PWTimeoutError, TalentaBotError) as exc:
        return _notify_error("critical", display_name, settings, notifier, exc.__class__.__name__, exc, page_for_shot=None)


def _notify_error(
    kind,
    display_name: str,
    settings: Settings,
    notifier: TelegramNotifier,
    category: str,
    exc: Exception,
    page_for_shot,
) -> int:
    ts = now_in_tz(settings.timezone)
    msg = build_message(kind=kind, action=display_name, ts=ts, category=category, reason=str(exc))
    # Screenshot only if we have a page reference (attendance-phase errors).
    # Login-phase errors have no screenshot — send text only.
    if page_for_shot is not None:
        shot = _screenshot(page_for_shot, settings.state_dir, category)
        if shot:
            notifier.send_photo(caption=msg, photo_path=shot)
            return 1
    notifier.send_text(msg)
    return 1


@app.command("clock-in")
def clock_in_cmd(
    now: bool = typer.Option(False, "--now", help="Skip random sleep"),
    skip_window: bool = typer.Option(False, "--skip-window", help="Skip weekday check"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Do not click, just navigate"),
) -> None:
    rc = _run_action("clock-in", now=now, skip_window=skip_window, dry_run=dry_run)
    raise typer.Exit(rc)


@app.command("clock-out")
def clock_out_cmd(
    now: bool = typer.Option(False, "--now"),
    skip_window: bool = typer.Option(False, "--skip-window"),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    rc = _run_action("clock-out", now=now, skip_window=skip_window, dry_run=dry_run)
    raise typer.Exit(rc)


@app.command("login")
def login_cmd() -> None:
    """Force login and persist storage_state. Useful for first-time setup."""
    settings = _load_settings()
    with playwright_page(settings) as (page, _ctx):
        logger.info("logged in at %s — storage_state will persist on exit", page.url)
    raise typer.Exit(0)


if __name__ == "__main__":
    app()
```

> **Note:** the error handlers currently pass `page_for_shot=None` because the `with` block closes before reaching the `except`. A future improvement (deferred to smoke-phase debugging) is to move the try/except inside the `with` block so errors mid-attendance capture the live page. For v1 the screenshot work is done by the dedicated error paths; text-only notification is acceptable for login-phase errors per the spec's credential-leak mitigation.

- [ ] **Step 2: Sanity import & help**

```bash
python -m talenta_bot --help
```

Expected: typer help listing `clock-in`, `clock-out`, `login`.

- [ ] **Step 3: Commit**

```bash
git add src/talenta_bot/cli.py
git commit -m "feat(cli): orchestration with error taxonomy"
```

---

## Task 11: Improve error screenshot — capture live page

**Files:**
- Modify: `src/talenta_bot/cli.py`

The v1 in Task 10 left attendance-phase screenshots unfilled. Make errors inside the `with playwright_page(...)` block capture the live `page` before it closes.

- [ ] **Step 1: Refactor `_run_action` to catch inside `with`**

Replace the body of `_run_action` from "try: ... with playwright_page..." downwards with:

```python
    display_name = "Clock In" if action == "clock-in" else "Clock Out"
    already_fn = att.already_clocked_in_today if action == "clock-in" else att.already_clocked_out_today
    click_fn = att.click_clock_in if action == "clock-in" else att.click_clock_out

    try:
        with playwright_page(settings) as (page, _ctx):
            try:
                existing = already_fn(page)
                if existing:
                    msg = build_message(
                        kind="info",
                        action=display_name,
                        ts=now_in_tz(settings.timezone),
                        note=f"tercatat {existing} (manual)",
                    )
                    notifier.send_text(msg)
                    return 0

                if dry_run:
                    logger.info("dry-run: would click %s button", display_name)
                    return 0

                click_fn(page)
                msg = build_message(
                    kind="success",
                    action=display_name,
                    ts=now_in_tz(settings.timezone),
                )
                notifier.send_text(msg)
                return 0
            except TalentaBotError as exc:
                return _notify_error(
                    _kind_for(exc),
                    display_name,
                    settings,
                    notifier,
                    exc.category,
                    exc,
                    page_for_shot=page,
                )
    except LoginFailed as exc:
        # login errors: no page available yet (context not yielded)
        return _notify_error("critical", display_name, settings, notifier, "LoginFailed", exc, page_for_shot=None)
    except TalentaDown as exc:
        return _notify_error("warning", display_name, settings, notifier, "TalentaDown", exc, page_for_shot=None)
    except PWTimeoutError as exc:
        return _notify_error("critical", display_name, settings, notifier, "PWTimeoutError", exc, page_for_shot=None)
```

And add above `_notify_error`:

```python
def _kind_for(exc: TalentaBotError) -> str:
    mapping = {
        "LoginFailed": "critical",
        "SelectorNotFound": "critical",
        "TalentaDown": "warning",
        "ClockActionFailed": "warning",
    }
    return mapping.get(exc.category, "critical")
```

- [ ] **Step 2: Smoke check — still imports**

```bash
python -m talenta_bot --help
```

- [ ] **Step 3: Commit**

```bash
git add src/talenta_bot/cli.py
git commit -m "refactor(cli): capture screenshot from live page on attendance errors"
```

---

## Task 12: Integration Test — Mock Talenta Happy Path

**Files:**
- Create: `tests/integration/conftest.py`
- Create: `tests/integration/test_clock_in_happy_path.py`

- [ ] **Step 1: Add a mock server fixture**

```python
# tests/integration/conftest.py
import asyncio
import threading
from pathlib import Path

import pytest
from aiohttp import web


class MockTalenta:
    """Minimal stand-in for Mekari SSO + Talenta dashboard + action endpoint."""

    def __init__(self):
        self.app = web.Application()
        self.app.router.add_get("/users/sign_in", self._login_page)
        self.app.router.add_post("/users/sign_in", self._do_login)
        self.app.router.add_get("/", self._dashboard)
        self.app.router.add_get("/live-attendance", self._live_attendance)
        self.app.router.add_post("/api/clock-in", self._do_clock_in)
        self.calls = []
        self.clock_in_recorded = False

    async def _login_page(self, request):
        return web.Response(
            text="""
            <html><body>
              <form method='post' action='/users/sign_in'>
                <input name='user[email]'/>
                <input name='user[password]' type='password'/>
                <button type='submit'>Sign in</button>
              </form>
            </body></html>
            """,
            content_type="text/html",
        )

    async def _do_login(self, request):
        data = await request.post()
        if data.get("user[email]") and data.get("user[password]"):
            resp = web.HTTPFound("/")
            resp.set_cookie("session", "ok")
            return resp
        return web.Response(status=401, text="<div class='alert-danger'>bad credentials</div>",
                            content_type="text/html")

    async def _dashboard(self, request):
        if request.cookies.get("session") != "ok":
            return web.HTTPFound("/users/sign_in")
        return web.Response(text="<html><body>dashboard</body></html>", content_type="text/html")

    async def _live_attendance(self, request):
        if request.cookies.get("session") != "ok":
            return web.HTTPFound("/users/sign_in")
        time_html = (
            "<div data-testid='clock-in-time'>08:07</div>"
            if self.clock_in_recorded else ""
        )
        return web.Response(
            text=f"""
            <html><body>
              <div data-testid='today-attendance-card'>{time_html}</div>
              <button onclick="fetch('/api/clock-in',{{method:'POST'}}).then(()=>document.body.innerHTML+='<div class=toast-success>ok</div>')">Clock In</button>
            </body></html>
            """,
            content_type="text/html",
        )

    async def _do_clock_in(self, request):
        self.calls.append(("clock-in", await request.text()))
        self.clock_in_recorded = True
        return web.json_response({"ok": True})


@pytest.fixture
def mock_talenta():
    server = MockTalenta()

    loop = asyncio.new_event_loop()
    runner = web.AppRunner(server.app)
    site_holder = {}

    def run():
        asyncio.set_event_loop(loop)
        loop.run_until_complete(runner.setup())
        site = web.TCPSite(runner, "127.0.0.1", 0)
        loop.run_until_complete(site.start())
        site_holder["port"] = site._server.sockets[0].getsockname()[1]
        loop.run_forever()

    t = threading.Thread(target=run, daemon=True)
    t.start()
    # Busy-wait for port
    while "port" not in site_holder:
        pass

    base = f"http://127.0.0.1:{site_holder['port']}"
    try:
        yield server, base
    finally:
        loop.call_soon_threadsafe(loop.stop)
```

- [ ] **Step 2: Write the happy-path test**

```python
# tests/integration/test_clock_in_happy_path.py
import os

import pytest

from talenta_bot import cli, selectors


@pytest.mark.skipif(
    not os.environ.get("RUN_INTEGRATION"),
    reason="set RUN_INTEGRATION=1 to run — needs Chromium installed",
)
def test_clock_in_flow_against_mock(mock_talenta, tmp_path, monkeypatch):
    server, base = mock_talenta

    # Point selectors + session at the mock
    monkeypatch.setattr(selectors, "SSO_LOGIN_URL", f"{base}/users/sign_in")
    monkeypatch.setattr(selectors, "TALENTA_BASE_URL", base)
    monkeypatch.setattr(selectors, "LIVE_ATTENDANCE_URL", f"{base}/live-attendance")
    monkeypatch.setattr(selectors, "DASHBOARD_URL_PATTERN", f"{base}/**")

    # Env: valid settings pointing to mock
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

    # Stub Telegram to avoid real requests
    sent = []
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
```

- [ ] **Step 3: Install Chromium and run**

```bash
playwright install chromium
RUN_INTEGRATION=1 pytest tests/integration/ -v
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add tests/integration/
git commit -m "test(integration): clock-in happy path vs mock Talenta"
```

---

## Task 13: Dockerfile

**Files:**
- Create: `Dockerfile`
- Create: `.dockerignore`

- [ ] **Step 1: Write Dockerfile**

```dockerfile
# Dockerfile
FROM mcr.microsoft.com/playwright/python:v1.49.0-jammy

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    TZ=Asia/Jakarta

# supercronic — cron alternative for containers (logs to stdout)
ARG SUPERCRONIC_VERSION=v0.2.33
ARG SUPERCRONIC_SHA256=71b0d58cc53f6bd72cf2f293e09e294b79c666d8f25f6a3b5e8033e2eefc1b6a
RUN curl -fsSLo /usr/local/bin/supercronic \
      "https://github.com/aptible/supercronic/releases/download/${SUPERCRONIC_VERSION}/supercronic-linux-amd64" \
 && echo "${SUPERCRONIC_SHA256}  /usr/local/bin/supercronic" | sha256sum -c - \
 && chmod +x /usr/local/bin/supercronic

WORKDIR /app
COPY pyproject.toml ./
COPY src/ ./src/
RUN pip install --no-cache-dir -e .

COPY crontab ./crontab

# Non-root user
RUN useradd -m -u 1000 bot \
 && mkdir -p /app/state \
 && chown -R bot:bot /app
USER bot

CMD ["supercronic", "/app/crontab"]
```

> **Note on SHA256:** the sha above is an illustrative placeholder; after downloading the binary locally, run `sha256sum supercronic-linux-amd64` and replace. This enforces reproducible builds.

- [ ] **Step 2: Write `.dockerignore`**

```
.git
.gitignore
.venv
.env
.pytest_cache
.ruff_cache
__pycache__
state/
tests/
docs/
*.md
```

- [ ] **Step 3: Build locally and verify**

```bash
docker build -t talenta-bot:dev .
docker run --rm talenta-bot:dev python -c "import talenta_bot; print(talenta_bot.__version__)"
```

Expected: `0.1.0`.

- [ ] **Step 4: Commit**

```bash
git add Dockerfile .dockerignore
git commit -m "build: Dockerfile on Playwright base with supercronic"
```

---

## Task 14: docker-compose + crontab

**Files:**
- Create: `docker-compose.yml`
- Create: `crontab`

- [ ] **Step 1: Write `crontab`**

```cron
# m h dom mon dow  command
# Primary clock-in + 30-min backstop (Mon-Fri)
  0  8   *   *   1-5   cd /app && python -m talenta_bot clock-in
  30 8   *   *   1-5   cd /app && python -m talenta_bot clock-in
# Primary clock-out + 30-min backstop
  0  17  *   *   1-5   cd /app && python -m talenta_bot clock-out
  30 17  *   *   1-5   cd /app && python -m talenta_bot clock-out
```

- [ ] **Step 2: Write `docker-compose.yml`**

```yaml
services:
  talenta-bot:
    build: .
    image: talenta-bot:latest
    container_name: talenta-bot
    restart: unless-stopped
    env_file: .env
    environment:
      TZ: Asia/Jakarta
    volumes:
      - ./state:/app/state
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"
```

- [ ] **Step 3: Verify compose parses**

```bash
docker compose config
```

Expected: rendered config with no errors.

- [ ] **Step 4: Commit**

```bash
git add docker-compose.yml crontab
git commit -m "build: docker-compose service + supercronic crontab"
```

---

## Task 15: README and SMOKE checklist

**Files:**
- Create: `README.md`
- Create: `docs/SMOKE.md`

- [ ] **Step 1: Write `README.md`**

```markdown
# Talenta Auto Clock-In/Out

Runs unattended on a VPS via Docker. Clocks in and out on Talenta (Mekari HR)
on weekdays within configurable randomised windows, with Telegram notifications.

## Requirements

- Linux VPS with `docker` and `docker compose`
- Outbound HTTPS access to `*.mekari.com`, `*.talenta.co`, `api.telegram.org`
- Mekari account without 2FA
- Telegram bot token + chat id

## First-time setup

```bash
git clone <repo> ~/talenta-automation
cd ~/talenta-automation
cp .env.example .env && $EDITOR .env
mkdir -p state && chmod 700 state
chmod 600 .env

# One-time: warm up session
docker compose run --rm talenta-bot python -m talenta_bot login

# Start scheduler
docker compose up -d
docker compose logs -f talenta-bot   # verify supercronic output
```

## Operations

```bash
# Test a run manually (bypass schedule & window)
docker compose run --rm talenta-bot python -m talenta_bot clock-in --now --skip-window

# Dry-run (navigate, do not click)
docker compose run --rm talenta-bot python -m talenta_bot clock-in --dry-run

# Tail logs
docker compose logs --tail 100 talenta-bot

# Update
git pull && docker compose build && docker compose up -d
```

## Troubleshooting

- **LoginFailed**: verify `MEKARI_EMAIL` / `MEKARI_PASSWORD` in `.env`, then rerun `login`.
- **Session expired**: delete `state/storage_state.json` and run `login` again.
- **Selectors not found**: Talenta UI has likely changed — update `src/talenta_bot/selectors.py`.
- **No Telegram messages**: test `curl -d chat_id=... -d text=hi "https://api.telegram.org/bot<TOKEN>/sendMessage"`.

## Layout

See `docs/superpowers/specs/2026-04-16-talenta-automation-design.md` for the full design.
```

- [ ] **Step 2: Write `docs/SMOKE.md`**

```markdown
# Post-deploy smoke checklist

Run these after every `docker compose build && up -d`.

- [ ] `docker compose run --rm talenta-bot python -m talenta_bot login` → exit 0, `state/storage_state.json` now exists.
- [ ] `docker compose run --rm talenta-bot python -m talenta_bot clock-in --dry-run` → logs "would click Clock In button", exit 0.
- [ ] On a weekday, in window: `clock-in --now --skip-window` → ✅ Telegram message AND Talenta web shows today's entry.
- [ ] Remove `state/storage_state.json`, rerun `clock-in --now --skip-window` → auto-relogin, new state file appears.
- [ ] Put a wrong password in `.env`, run `clock-in --now --skip-window` → 🚨 Telegram message with "LoginFailed". Restore password after.
- [ ] `docker compose logs --tail 50` → supercronic "cron job started" lines visible.
```

- [ ] **Step 3: Commit**

```bash
git add README.md docs/SMOKE.md
git commit -m "docs: README + post-deploy smoke checklist"
```

---

## Task 16: Final verification

- [ ] **Step 1: Run full unit suite**

```bash
pytest tests/unit/ -v
```

Expected: all PASS in under 2 seconds.

- [ ] **Step 2: Run integration test**

```bash
RUN_INTEGRATION=1 pytest tests/integration/ -v
```

Expected: PASS.

- [ ] **Step 3: Lint**

```bash
ruff check src/ tests/
ruff format --check src/ tests/
```

Expected: clean (or fix auto-fixable issues).

- [ ] **Step 4: Verify Docker build**

```bash
docker compose build
docker compose config
```

Expected: build succeeds, compose config renders.

- [ ] **Step 5: Commit any last fixups**

```bash
git status
git add -A && git commit -m "chore: final cleanup" || echo "nothing to commit"
```

- [ ] **Step 6: Execute the SMOKE checklist on the real VPS** (manual — user-driven, outside automation scope).

---

## Spec Coverage Check

| Spec section | Task(s) |
|---|---|
| Functional req 1 (windowed schedule) | 3 (scheduler), 14 (cron), 10 (CLI wires them) |
| Functional req 2 (idempotency) | 9 (already_clocked_*), 10 (CLI skip path) |
| Functional req 3 (session persistence) | 8 (playwright_page, STATE_TTL, relogin) |
| Functional req 4 (geolocation override) | 7, 8 (jittered_coords + context kwargs) |
| Functional req 5 (one notification per run) | 10, 11 (CLI orchestration) |
| Functional req 6 (screenshot on error) | 11 (attendance-phase), 10 (text-only for login) |
| Functional req 7 (backstop run) | 14 (crontab) + 9 (idempotency) |
| Non-functional: validation at startup | 2 (pydantic validators) |
| Non-functional: non-root container | 13 (Dockerfile `USER bot`) |
| Non-functional: log rotation | 14 (compose logging driver) |
| Error taxonomy | 4 (errors), 10, 11 (CLI dispatching) |
| Unit tests (config, scheduler, notifier, session helper) | 2, 3, 6, 7 |
| Integration test | 12 |
| Manual smoke | 15 (SMOKE.md) |
| Docker image + compose | 13, 14 |
| README + ops docs | 15 |
