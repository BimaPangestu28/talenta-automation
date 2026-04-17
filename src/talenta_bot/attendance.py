from __future__ import annotations

import logging

from playwright.sync_api import Page
from playwright.sync_api import TimeoutError as PWTimeoutError

from talenta_bot import selectors
from talenta_bot.errors import ClockActionFailed, SelectorNotFound

logger = logging.getLogger(__name__)

WAIT_SELECTOR_MS = 15_000
WAIT_CONFIRM_MS = 15_000


def _goto_live_attendance(page: Page) -> None:
    page.goto(selectors.LIVE_ATTENDANCE_URL, wait_until="domcontentloaded", timeout=20_000)


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
    return _time_text(page, selectors.CLOCK_IN_TIME_DISPLAY)


def already_clocked_out_today(page: Page) -> str | None:
    _goto_live_attendance(page)
    return _time_text(page, selectors.CLOCK_OUT_TIME_DISPLAY)


def _click_and_confirm(page: Page, button_selector: str, action_name: str) -> None:
    try:
        page.wait_for_selector(button_selector, timeout=WAIT_SELECTOR_MS)
    except PWTimeoutError as exc:
        raise SelectorNotFound(
            f"{action_name}: button {button_selector!r} not found"
        ) from exc

    # Log every network request while the action is in progress — helps
    # debug silent backend failures (geolocation rejects, 4xx, etc.)
    api_calls: list[str] = []

    def on_response(resp):
        is_talenta_host = "talenta.co" in resp.url or "mekari.com" in resp.url
        is_attendance_endpoint = any(
            kw in resp.url for kw in ("clock", "attendance", "check-in", "check-out")
        )
        if is_talenta_host and is_attendance_endpoint:
            api_calls.append(f"{resp.status} {resp.request.method} {resp.url}")

    page.on("response", on_response)
    try:
        page.click(button_selector)
        try:
            page.wait_for_selector(
                f"{selectors.ACTION_SUCCESS_TOAST}, {selectors.CLOCK_IN_TIME_DISPLAY}, "
                f"{selectors.CLOCK_OUT_TIME_DISPLAY}",
                timeout=WAIT_CONFIRM_MS,
            )
        except PWTimeoutError as exc:
            err = _time_text(page, selectors.ACTION_ERROR_TOAST) or "no confirmation within 15s"
            if api_calls:
                err = f"{err}; calls={api_calls}"
            else:
                err = f"{err}; no attendance API call detected"
            raise ClockActionFailed(f"{action_name}: {err}") from exc
    finally:
        page.remove_listener("response", on_response)


def click_clock_in(page: Page) -> None:
    logger.info("clicking Clock In")
    _click_and_confirm(page, selectors.CLOCK_IN_BUTTON, "Clock In")


def click_clock_out(page: Page) -> None:
    logger.info("clicking Clock Out")
    _click_and_confirm(page, selectors.CLOCK_OUT_BUTTON, "Clock Out")
