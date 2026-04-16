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
