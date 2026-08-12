import os
from dotenv import load_dotenv

load_dotenv()


class Settings:

    YAHOO_FINANCE_ENABLED = (
        os.getenv("YAHOO_FINANCE_ENABLED", "true").lower() == "true"
    )
    YAHOO_CACHE_TTL_SECONDS = int(
        os.getenv("YAHOO_CACHE_TTL_SECONDS", "60")
    )
    YAHOO_TIMEOUT_SECONDS = int(
        os.getenv("YAHOO_TIMEOUT_SECONDS", "10")
    )
    YAHOO_MAX_NEWS = int(
        os.getenv("YAHOO_MAX_NEWS", "5")
    )
settings = Settings()