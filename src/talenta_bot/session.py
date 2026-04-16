from __future__ import annotations

import logging
import math
import random
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from playwright.sync_api import (
    BrowserContext,
    Page,
    sync_playwright,
)
from playwright.sync_api import (
    TimeoutError as PWTimeoutError,
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


def jittered_coords(lat: float, lon: float, max_meters: float) -> tuple[float, float]:
    """Return (lat, lon) offset by a uniform-random vector of length ≤ max_meters."""
    if max_meters <= 0:
        return lat, lon
    theta = random.uniform(0, 2 * math.pi)
    r = max_meters * math.sqrt(random.random())
    d_lat = (r * math.cos(theta)) / 111_000
    d_lon = (r * math.sin(theta)) / (111_000 * math.cos(math.radians(lat)))
    return lat + d_lat, lon + d_lon


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
        if "account.mekari.com" not in page.url:
            page.goto(SSO_LOGIN_URL, timeout=20_000)

        page.wait_for_selector(SSO_EMAIL_INPUT, timeout=10_000)
        page.fill(SSO_EMAIL_INPUT, email)

        if SSO_IS_TWO_STEP:
            page.click(SSO_SUBMIT_BUTTON)
            page.wait_for_selector(SSO_PASSWORD_INPUT, timeout=10_000)

        page.fill(SSO_PASSWORD_INPUT, password)
        page.click(SSO_SUBMIT_BUTTON)

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
