from datetime import datetime, timezone
from typing import Optional


def as_utc(value: Optional[datetime]) -> datetime:
    """Return a timezone-aware UTC datetime.

    SQLite (used in tests) drops timezone information, so values read
    back from the database can be naive.
    """

    if value is None:
        return datetime.min.replace(tzinfo=timezone.utc)

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)
