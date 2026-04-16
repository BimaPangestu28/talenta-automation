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
from talenta_bot import selectors
from talenta_bot.config import Settings
from talenta_bot.errors import (
    ConfigError,
    LoginFailed,
    SelectorNotFound,
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

_KIND_BY_CATEGORY = {
    "LoginFailed": "critical",
    "SelectorNotFound": "critical",
    "TalentaDown": "warning",
    "ClockActionFailed": "warning",
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


def _notify_error(
    kind: str,
    display_name: str,
    settings: Settings,
    notifier: TelegramNotifier,
    category: str,
    exc: Exception,
    page_for_shot,
) -> int:
    ts = now_in_tz(settings.timezone)
    msg = build_message(
        kind=kind, action=display_name, ts=ts, category=category, reason=str(exc)
    )
    if page_for_shot is not None:
        shot = _screenshot(page_for_shot, settings.state_dir, category)
        if shot:
            notifier.send_photo(caption=msg, photo_path=shot)
            return 1
    notifier.send_text(msg)
    return 1


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
    already_fn = (
        att.already_clocked_in_today if action == "clock-in" else att.already_clocked_out_today
    )
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
                    button_selector = (
                        selectors.CLOCK_IN_BUTTON
                        if action == "clock-in"
                        else selectors.CLOCK_OUT_BUTTON
                    )
                    try:
                        page.wait_for_selector(button_selector, timeout=15_000)
                    except PWTimeoutError as exc:
                        raise SelectorNotFound(
                            f"{display_name}: button {button_selector!r} not found"
                        ) from exc
                    logger.info(
                        "dry-run: %s button is reachable — would click here in real run",
                        display_name,
                    )
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
                    _KIND_BY_CATEGORY.get(exc.category, "critical"),
                    display_name,
                    settings,
                    notifier,
                    exc.category,
                    exc,
                    page_for_shot=page,
                )
    except LoginFailed as exc:
        return _notify_error(
            "critical", display_name, settings, notifier, "LoginFailed", exc, page_for_shot=None
        )
    except TalentaDown as exc:
        return _notify_error(
            "warning", display_name, settings, notifier, "TalentaDown", exc, page_for_shot=None
        )
    except PWTimeoutError as exc:
        return _notify_error(
            "critical",
            display_name,
            settings,
            notifier,
            "PWTimeoutError",
            exc,
            page_for_shot=None,
        )


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
def login_cmd(
    interactive: bool = typer.Option(
        False,
        "--interactive/--auto",
        help=(
            "Auto (default): fill email+password and submit the Mekari form. "
            "Interactive: launch a visible browser for manual login — needed only "
            "if the account requires Google OAuth, 2FA, SAML, or any flow beyond "
            "plain email+password."
        ),
    ),
) -> None:
    """First-time login. Saves state/storage_state.json for later headless reuse."""
    settings = _load_settings()
    if interactive:
        _interactive_login(settings)
    else:
        with playwright_page(settings) as (page, _ctx):
            logger.info("logged in at %s — storage_state will persist on exit", page.url)
    raise typer.Exit(0)


def _interactive_login(settings: Settings) -> None:
    """Launch a visible browser and wait until the user reaches hr.talenta.co."""
    from playwright.sync_api import sync_playwright

    from talenta_bot import selectors
    from talenta_bot.session import DEFAULT_UA, _storage_state_path

    state_path = _storage_state_path(settings.state_dir)
    settings.state_dir.mkdir(parents=True, exist_ok=True)

    print(
        "Opening a browser. Complete login manually (Google OAuth, 2FA, whatever).\n"
        "The session will be saved once you reach hr.talenta.co.\n"
        "Timeout: 5 minutes."
    )

    with sync_playwright() as pw:
        # Always visible — interactive login does not use headless.
        browser = pw.chromium.launch(headless=False)
        context = browser.new_context(
            locale="id-ID",
            timezone_id=settings.timezone,
            viewport={"width": 1280, "height": 800},
            user_agent=DEFAULT_UA,
        )
        page = context.new_page()
        page.goto(selectors.SSO_LOGIN_URL)
        try:
            page.wait_for_url("**/hr.talenta.co/**", timeout=300_000)
        except Exception as exc:
            browser.close()
            raise SystemExit(f"Did not reach hr.talenta.co within 5 min: {exc}") from exc

        context.storage_state(path=str(state_path))
        browser.close()
        print(f"Session saved to {state_path}")


if __name__ == "__main__":
    app()
