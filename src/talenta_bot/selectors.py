"""Captured selectors for Mekari SSO and Talenta dashboard.

NOTE: These are best-guess defaults from the design spec. They must be
verified against the live site during smoke testing. Update whenever
upstream UI changes.
"""

# --- Mekari SSO (account.mekari.com) ---
SSO_LOGIN_URL = (
    "https://account.mekari.com/users/sign_in"
    "?client_id=TAL-73645&return_to=L2F1dGg_Y2xpZW50X2lkPVRBTC03MzY0NSZyZXNwb25zZV90eXBlPWNvZGUmc2NvcGU9c3NvOnByb2ZpbGU%3D"
)
SSO_EMAIL_INPUT = "#user_email"
SSO_PASSWORD_INPUT = "#user_password"
# The form uses <input type="submit" id="new-signin-button">. Targeting by
# ID avoids matching the separate "Sign in dengan Google" <button> that sits
# in its own OAuth form below the native email/password form.
SSO_SUBMIT_BUTTON = "#new-signin-button"
SSO_ERROR_BANNER = "#alert-danger-fe .alert-body p, .alert-danger"
SSO_IS_TWO_STEP = False  # Mekari form takes email+password in a single step

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
