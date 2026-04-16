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
