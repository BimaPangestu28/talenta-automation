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
