import os
from dotenv import load_dotenv

load_dotenv()


def _get_int(name: str, default: int) -> int:
    raw = os.getenv(name)

    if raw is None or not raw.strip():
        return default

    try:
        return int(raw)
    except ValueError:
        return default


class Settings:

    YAHOO_FINANCE_ENABLED = (
        os.getenv("YAHOO_FINANCE_ENABLED", "true").lower() == "true"
    )
    YAHOO_CACHE_TTL_SECONDS = _get_int("YAHOO_CACHE_TTL_SECONDS", 60)
    YAHOO_TIMEOUT_SECONDS = _get_int("YAHOO_TIMEOUT_SECONDS", 10)
    YAHOO_MAX_NEWS = _get_int("YAHOO_MAX_NEWS", 5)

    # -----------------------------------------------------
    # Google OAuth / APIs
    # -----------------------------------------------------

    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
    GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "")

    # Fernet key used to encrypt OAuth tokens at rest.
    # Generate with:
    #   python -c "from cryptography.fernet import Fernet;
    #              print(Fernet.generate_key().decode())"
    GOOGLE_TOKEN_ENCRYPTION_KEY = os.getenv(
        "GOOGLE_TOKEN_ENCRYPTION_KEY", ""
    )

    GOOGLE_TIMEOUT_SECONDS = _get_int("GOOGLE_TIMEOUT_SECONDS", 15)
    GOOGLE_MAX_RETRIES = _get_int("GOOGLE_MAX_RETRIES", 3)
    GOOGLE_CACHE_TTL_SECONDS = _get_int("GOOGLE_CACHE_TTL_SECONDS", 60)
    GOOGLE_MAX_CONCURRENT_REQUESTS = _get_int(
        "GOOGLE_MAX_CONCURRENT_REQUESTS", 5
    )

    # How long an unused OAuth `state` value stays valid.
    GOOGLE_OAUTH_STATE_TTL_SECONDS = _get_int(
        "GOOGLE_OAUTH_STATE_TTL_SECONDS", 900
    )

    # Refresh the access token this many seconds before it expires.
    GOOGLE_TOKEN_REFRESH_LEEWAY_SECONDS = _get_int(
        "GOOGLE_TOKEN_REFRESH_LEEWAY_SECONDS", 120
    )

    # -----------------------------------------------------
    # Payload limits (keep tool results small enough for the LLM)
    # -----------------------------------------------------

    GMAIL_MAX_MESSAGES = _get_int("GMAIL_MAX_MESSAGES", 10)
    GMAIL_MAX_BODY_CHARS = _get_int("GMAIL_MAX_BODY_CHARS", 4000)
    CALENDAR_MAX_EVENTS = _get_int("CALENDAR_MAX_EVENTS", 20)
    DRIVE_MAX_FILES = _get_int("DRIVE_MAX_FILES", 20)
    DRIVE_MAX_FILE_CHARS = _get_int("DRIVE_MAX_FILE_CHARS", 6000)
    SHEETS_MAX_ROWS = _get_int("SHEETS_MAX_ROWS", 100)
    TOOL_RESULT_MAX_CHARS = _get_int("TOOL_RESULT_MAX_CHARS", 8000)

    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

    @property
    def google_oauth_configured(self) -> bool:
        return bool(
            self.GOOGLE_CLIENT_ID
            and self.GOOGLE_CLIENT_SECRET
            and self.GOOGLE_REDIRECT_URI
        )


settings = Settings()
