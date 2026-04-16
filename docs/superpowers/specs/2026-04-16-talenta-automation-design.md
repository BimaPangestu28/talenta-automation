# Talenta Auto Clock-In / Clock-Out Automation — Design

**Status:** Draft for review
**Date:** 2026-04-16
**Target platform:** Talenta by Mekari (https://hr.talenta.co) via Mekari SSO

## Purpose

Automate daily clock-in and clock-out on Talenta for a single user, running unattended on a VPS via Docker. Must be resilient to session expiry, idempotent against manual clock-ins from the mobile app, and notify the user on every outcome via Telegram.

## Scope

**In scope**
- Headless browser login to Mekari SSO (email + password, no MFA).
- Persisted Playwright `storage_state` to skip re-login between runs.
- Clock-in and clock-out flow with geolocation override.
- Idempotency check — skip if already clocked in/out for the day.
- Randomised timing within configurable windows.
- Weekday-only schedule (Mon–Fri).
- Telegram notifications (success, skip, error + screenshot).
- Docker deployment via `docker compose` with `supercronic` as in-container scheduler.

**Out of scope**
- Multiple users / multi-tenant.
- 2FA/MFA handling.
- Selfie capture, shift-picker, or approval workflows (user confirmed their company config does not require these).
- Scraping scheduled shifts from Talenta to drive timing.
- Host-level monitoring (VPS up/down).
- Indonesian public-holiday awareness (deferred; weekday-only is sufficient for now).

## Functional requirements

1. On weekdays, perform clock-in within a user-configured time window (default `08:00–08:15`) and clock-out within another window (default `17:05–17:30`), both local time (`Asia/Jakarta`).
2. Before attempting the action, check Talenta's own state — if already performed today, skip and notify informationally.
3. If session is valid (`storage_state.json` present and not stale), reuse it; otherwise perform SSO login and save a fresh state.
4. Override browser geolocation with configured office lat/long plus small random jitter (default ±5 m).
5. Every run MUST emit exactly one Telegram message unless it is a weekend skip (silent).
6. On error, attach a full-page screenshot to the Telegram message.
7. A backstop cron run 30 minutes after the primary run retries automatically; idempotency guarantees no double-clock.

## Non-functional requirements

- **Runtime env:** Single VPS, Linux, Docker + `docker compose` installed.
- **Resource budget:** ≤1 vCPU, ≤1 GB RAM at peak (Chromium headless).
- **Language/stack:** Python ≥3.11, Playwright for Python ≥1.49.
- **Secrets:** plain `.env` file, `chmod 600`, never committed.
- **Observability:** stdout → Docker logs (rotated 10 MB × 3); append-only run log at `state/last_run.log`.
- **Security:** container runs as non-root (`uid 1000`); no ports exposed; only outbound HTTPS to `*.mekari.com` / `*.talenta.co` / `api.telegram.org`.
- **Portability:** the whole system lives in one repo folder; `docker compose up -d` on any Linux host is the only setup step after cloning and filling `.env`.

## Architecture

### Directory layout

```
talenta-automation/
├── src/talenta_bot/
│   ├── __init__.py
│   ├── config.py          # env parsing + validation (pydantic-settings)
│   ├── session.py         # browser launch, storage_state, login
│   ├── attendance.py      # clock_in, clock_out, status check
│   ├── notifier.py        # Telegram messages + photo uploads
│   ├── scheduler.py       # random_sleep_seconds, is_workday
│   └── cli.py             # typer entrypoint: login | clock-in | clock-out
├── tests/
│   ├── unit/
│   └── integration/
├── state/                 # runtime, gitignored, volume-mounted
│   ├── storage_state.json
│   ├── last_run.log
│   └── err-<timestamp>.png
├── docs/
├── crontab                # supercronic schedule file
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── .env.example
├── .dockerignore
├── .gitignore
└── README.md
```

### Component responsibilities

| Module | Responsibility | Primary dependencies |
|---|---|---|
| `config` | Parse `.env` into a validated `Settings` object. Fail fast on missing/invalid values. | `pydantic-settings`, `python-dotenv` |
| `session` | Launch Chromium with geo override, load/save `storage_state.json`, detect logged-out state and relogin. | `playwright` |
| `attendance` | Check daily status, click "Clock In" / "Clock Out", confirm success. | `playwright` |
| `notifier` | Build category-specific messages, send via Bot API, attach screenshots. | `httpx` |
| `scheduler` | Determine `is_workday()`, compute `random_sleep_seconds()` within a window. | stdlib (`datetime`, `random`, `zoneinfo`) |
| `cli` | Orchestrate a single run: scheduler → session → attendance → notifier. Handle exception taxonomy. | `typer` |

### Runtime flow — per cron firing

```
cron trigger (e.g. 08:00 weekday)
  └── python -m talenta_bot clock-in
      ├── settings = Settings.load()                    # fail-fast on config
      ├── if not scheduler.is_workday(): exit 0         # silent
      ├── scheduler.random_sleep(window=CLOCK_IN_WINDOW)
      ├── with session.playwright_page() as page:
      │     ├── goto hr.talenta.co
      │     ├── if redirected to login: login_flow(); save_state()
      │     ├── if attendance.already_clocked_in_today(page):
      │     │     notifier.info("already clocked in at HH:MM")
      │     │     return
      │     ├── attendance.click_clock_in(page)
      │     └── notifier.success("Clock In HH:MM")
      └── on exception → notifier.error(category, screenshot) → exit 1
```

### Session persistence

- `storage_state.json` is saved after every successful login.
- Considered valid if file exists and mtime < 7 days. Older files are ignored (forcing relogin) as a defensive TTL; Mekari session TTL is not contractually documented.
- After every successful interaction that traversed the login flow, re-save.
- File permissions 600. Volume-mounted from host `./state`.

### Geolocation spoofing

- `BrowserContext.geolocation = {latitude, longitude, accuracy}` plus `permissions=['geolocation']`.
- Jitter applied per run: uniform random offset within `GEO_JITTER_METERS` radius. Approximate conversion: 1° lat ≈ 111 km, so `delta_lat = meters/111000`, `delta_long = meters/(111000 * cos(lat))`.
- Default jitter = 5 m. User can set 0 to disable.

## Configuration

All settings via `.env`, loaded by `pydantic-settings`. Template:

```env
MEKARI_EMAIL=you@example.com
MEKARI_PASSWORD=your-password

OFFICE_LAT=-6.200000
OFFICE_LONG=106.816666
GEO_JITTER_METERS=5

CLOCK_IN_WINDOW_START=08:00
CLOCK_IN_WINDOW_END=08:15
CLOCK_OUT_WINDOW_START=17:05
CLOCK_OUT_WINDOW_END=17:30
TIMEZONE=Asia/Jakarta

TELEGRAM_BOT_TOKEN=123456:ABC-xyz
TELEGRAM_CHAT_ID=12345678

STATE_DIR=/app/state
HEADLESS=true
```

Validation rules enforced at startup:
- Email non-empty and contains `@`.
- Password non-empty.
- `OFFICE_LAT` in `[-11.5, 6.5]`, `OFFICE_LONG` in `[94.5, 141.5]` (Indonesia bounding box — sanity check, not enforcement).
- Each window: `end > start`, both `HH:MM` format, both within a single day.
- `TELEGRAM_BOT_TOKEN` matches `/^\d+:[\w-]+$/`.
- `TIMEZONE` resolvable by `zoneinfo`.

## Error handling

### Error taxonomy

| Category | Trigger | Exit | Notify? | Retry in-run? |
|---|---|---|---|---|
| `SkippedWeekend` | `scheduler.is_workday()==False` | 0 | No | — |
| `SkippedAlreadyClocked` | Status check shows already done | 0 | Info (ℹ️) | — |
| `LoginFailed` | Credential rejected, SSO error | 1 | Critical (🚨) + screenshot | No |
| `TalentaDown` | `page.goto` timeout or 5xx | 1 | Warning (⚠️) | Once, after 5 s |
| `SelectorNotFound` | `wait_for_selector` timeout on UI element | 1 | Critical (🚨) + screenshot + HTML dump | No |
| `ClockActionFailed` | Click succeeded, no confirmation within 15 s | 1 | Warning (⚠️) + screenshot | No |
| `ConfigError` | Invalid/missing env at startup | 2 | Critical if Telegram reachable, else stderr | — |

### Retry strategy

- **In-run:** only `page.goto` retries once after 5 s (transient network).
- **Across runs:** primary at window start (:00), backstop at :30. Backstop auto-skips via idempotency. Maximum 2 attempts per day per action.

### Screenshot lifecycle

- Taken on any error before exit: `state/err-{iso-ts}-{category}.png`, full-page.
- Sent as Telegram `sendPhoto` (compressed, ≤10 MB API limit).
- Local retention: 7 days, auto-pruned at start of each run.

### Notification message format

```
✅ Clock In 08:07 WIB — Talenta OK
ℹ️ Clock In — skipped, tercatat 07:52 WIB (manual)
⚠️ Clock In gagal — TalentaDown (goto timeout 10s). Backstop jalan 08:30.
🚨 Clock In ERROR — LoginFailed: "Email atau password salah". Cek .env.
   [screenshot attached]
```

## Deployment

### Docker image

Base: `mcr.microsoft.com/playwright/python:v1.49.0-jammy` (official, includes Chromium + system deps).

Includes:
- `supercronic` binary (v0.2.33) for in-container cron, streams to stdout.
- Application source installed editable via `pip install -e .`.
- Non-root user `bot` (uid 1000).
- Default `CMD ["supercronic", "/app/crontab"]`.

### Schedule — `crontab` inside container

```cron
# min hour dom mon dow  command
  0   8   *   *   1-5  python -m talenta_bot clock-in
  30  8   *   *   1-5  python -m talenta_bot clock-in
  0   17  *   *   1-5  python -m talenta_bot clock-out
  30  17  *   *   1-5  python -m talenta_bot clock-out
```

Randomisation within the window is handled inside Python (`scheduler.random_sleep`). Cron only triggers at the edges.

### `docker-compose.yml`

```yaml
services:
  talenta-bot:
    build: .
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

### Bootstrap (VPS first-time)

```bash
git clone <repo> ~/talenta-automation && cd ~/talenta-automation
cp .env.example .env && $EDITOR .env           # fill credentials
mkdir -p state && chmod 700 state
docker compose run --rm talenta-bot python -m talenta_bot login   # warm up session
docker compose up -d
docker compose logs -f talenta-bot             # verify supercronic loaded
```

### CLI commands

| Command | Behaviour |
|---|---|
| `python -m talenta_bot login` | Interactive-capable login, saves `storage_state.json`, exits. |
| `python -m talenta_bot clock-in` | Full flow including weekday check and random sleep. |
| `python -m talenta_bot clock-out` | As above for clock-out. |
| `... clock-in --now` | Skip random sleep. |
| `... clock-in --skip-window` | Also skip weekday check (for testing). |
| `... clock-in --dry-run` | Navigate and identify target element, do NOT click. |

## Testing

### Unit (`tests/unit/`) — fast, run on save

| Module | Cases |
|---|---|
| `config.py` | Parse valid env; reject bad lat/long; reject malformed window; reject bad Telegram token; reject missing email/password. |
| `scheduler.py::is_workday` | Mon–Fri True, Sat/Sun False, timezone-aware. |
| `scheduler.py::random_sleep_seconds` | 1000 samples all within `[0, window_duration]`; distribution roughly uniform. |
| `notifier.py::build_message` | Correct emoji + format per category; timestamp rendered in configured TZ. |
| `session.py::jittered_coords` | 1000 samples all within `GEO_JITTER_METERS` of origin. |

Target: <2 s wall clock for the suite. Freeze time via `freezegun`.

### Integration (`tests/integration/`) — one test, mock server

`test_clock_in_happy_path.py`:
1. Start a local `aiohttp` server mocking Mekari SSO and Talenta attendance endpoints.
2. Override `HR_TALENTA_BASE_URL` / `MEKARI_AUTH_BASE_URL` via env.
3. Run `cli.clock_in()` end-to-end against the mock.
4. Assert: correct POST payload to the mock attendance endpoint; notifier called with `success` category.

One integration test is enough — its job is to catch regressions in orchestration wiring, not exhaustive live-site coverage.

### Manual smoke — `docs/SMOKE.md`

Checklist run after every deploy:
- [ ] `login` command produces a populated `storage_state.json`.
- [ ] `clock-in --dry-run` reports the element it would click.
- [ ] `clock-in --now --skip-window` during a valid work day produces a ✅ Telegram message AND a visible entry on Talenta web.
- [ ] Deleting `storage_state.json` triggers auto-relogin, verified by presence of a new file after next run.
- [ ] Wrong password in `.env` produces a 🚨 Telegram message with screenshot.
- [ ] `docker compose logs -f talenta-bot` shows supercronic announcing scheduled jobs.

### Deliberately not tested

- Live Talenta end-to-end in CI (credential risk, rate limits).
- Screenshot pixel diffing (overkill for internal tool).
- Coverage threshold gates.

## Risks & mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Talenta UI change breaks selectors | Medium | High | Screenshot+HTML on `SelectorNotFound`; selectors kept in one file (`attendance.py`) with explicit constants for quick patching. |
| Mekari adds 2FA to account | Low (user controls) | High | Not in scope; user notified via `LoginFailed`. Can extend later. |
| Employer detects automation from pattern | Low | High | Randomised timing, jittered geolocation, real Chromium UA. Not an evasion tool — user accepts this risk. |
| VPS clock drifts | Low | Medium | Rely on host NTP; document in README. |
| Credential leak via screenshot | Low | High | Password fields render as masked dots and are never captured. Email may be visible on `LoginFailed` screenshots — acceptable since user's own Telegram chat is the only destination. |

## Open questions (decided during brainstorming)

- Runtime: **VPS + Docker**.
- Clock-in form requirements: **button + GPS only**.
- Timing: **randomised window, Mon–Fri only**.
- Notification: **Telegram bot**.
- Idempotency: **check status first, skip if already done**.
- MFA: **none**.
- Stack: **Python + Playwright**.
- Approach: **Playwright with persisted `storage_state`**.

## Out of scope for v1 (possible future work)

- Public-holiday skip (Indonesia calendar API or static list).
- Reading Talenta shift schedule to drive timing dynamically.
- Secrets via `age`/`sops` or systemd credentials instead of plain `.env`.
- Healthcheck endpoint (container is long-running; Docker HEALTHCHECK possible).
- Multi-user support.
