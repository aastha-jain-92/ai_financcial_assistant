"""Service names, scopes and API endpoints for the Google integration."""

GMAIL = "gmail"
GOOGLE_CALENDAR = "google_calendar"
GOOGLE_DRIVE = "google_drive"
GOOGLE_SHEETS = "google_sheets"

SUPPORTED_SERVICES = (
    GMAIL,
    GOOGLE_CALENDAR,
    GOOGLE_DRIVE,
    GOOGLE_SHEETS,
)

SERVICE_LABELS = {
    GMAIL: "📧 Gmail",
    GOOGLE_CALENDAR: "📅 Google Calendar",
    GOOGLE_DRIVE: "📁 Google Drive",
    GOOGLE_SHEETS: "📊 Google Sheets",
}

BASE_SCOPES = (
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
)

SERVICE_SCOPES = {
    GMAIL: BASE_SCOPES + (
        "https://www.googleapis.com/auth/gmail.readonly",
    ),
    GOOGLE_CALENDAR: BASE_SCOPES + (
        "https://www.googleapis.com/auth/calendar.readonly",
    ),
    GOOGLE_DRIVE: BASE_SCOPES + (
        "https://www.googleapis.com/auth/drive.readonly",
    ),
    GOOGLE_SHEETS: BASE_SCOPES + (
        "https://www.googleapis.com/auth/spreadsheets.readonly",
        "https://www.googleapis.com/auth/drive.readonly",
    ),
}

AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
REVOKE_ENDPOINT = "https://oauth2.googleapis.com/revoke"
USERINFO_ENDPOINT = "https://openidconnect.googleapis.com/v1/userinfo"

GMAIL_API = "https://gmail.googleapis.com/gmail/v1"
CALENDAR_API = "https://www.googleapis.com/calendar/v3"
DRIVE_API = "https://www.googleapis.com/drive/v3"
SHEETS_API = "https://sheets.googleapis.com/v4/spreadsheets"


def normalize_service(service_name: str) -> str:
    """Map user/LLM supplied aliases onto canonical service names."""

    value = (service_name or "").strip().lower().replace("-", "_")
    value = value.replace(" ", "_")

    aliases = {
        "mail": GMAIL,
        "email": GMAIL,
        "google_mail": GMAIL,
        "calendar": GOOGLE_CALENDAR,
        "gcal": GOOGLE_CALENDAR,
        "drive": GOOGLE_DRIVE,
        "sheets": GOOGLE_SHEETS,
        "google_sheet": GOOGLE_SHEETS,
        "spreadsheets": GOOGLE_SHEETS,
    }

    return aliases.get(value, value)
