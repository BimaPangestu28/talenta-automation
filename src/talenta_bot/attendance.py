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


ATTENDANCE_CLOCKS_MARKER = "attendance_clocks"


def _click_and_confirm(page: Page, button_selector: str, action_name: str) -> None:
    try:
        page.wait_for_selector(button_selector, timeout=WAIT_SELECTOR_MS)
    except PWTimeoutError as exc:
        raise SelectorNotFound(
            f"{action_name}: button {button_selector!r} not found"
        ) from exc

    # Success is determined by the Talenta backend, not by DOM sniffing:
    # a POST to .../attendance_clocks returning 2xx is the ground truth
    # that the record was created.
    api_status: dict[str, int] = {}

    def on_response(resp):
        if ATTENDANCE_CLOCKS_MARKER in resp.url and resp.request.method == "POST":
            api_status["status"] = resp.status
            api_status["url"] = resp.url

    page.on("response", on_response)
    try:
        page.click(button_selector)

        # Poll for up to WAIT_CONFIRM_MS for the attendance_clocks response.
        deadline_ms = WAIT_CONFIRM_MS
        elapsed = 0
        poll_interval = 250
        while elapsed < deadline_ms:
            if "status" in api_status:
                break
            page.wait_for_timeout(poll_interval)
            elapsed += poll_interval

        if "status" not in api_status:
            err = _time_text(page, selectors.ACTION_ERROR_TOAST) or "no attendance API call"
            raise ClockActionFailed(f"{action_name}: {err}")

        status = api_status["status"]
        if status >= 400:
            raise ClockActionFailed(f"{action_name}: API returned {status}")
        # status is 2xx — record created.
    finally:
        page.remove_listener("response", on_response)


def click_clock_in(page: Page) -> None:
    logger.info("clicking Clock In")
    _click_and_confirm(page, selectors.CLOCK_IN_BUTTON, "Clock In")


def click_clock_out(page: Page) -> None:
    logger.info("clicking Clock Out")
    _click_and_confirm(page, selectors.CLOCK_OUT_BUTTON, "Clock Out")
