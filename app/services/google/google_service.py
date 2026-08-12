"""User-facing Google data access used by the LLM tool layer.

Every method:

1. resolves a valid OAuth access token for the user + service,
2. calls the Google API through the provider layer,
3. retries once with a forced token refresh on a 401,
4. returns plain dicts/lists that are cheap to serialise for the LLM.
"""

import hashlib
import json
import logging
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.providers.google import (
    GMAIL,
    GOOGLE_CALENDAR,
    GOOGLE_DRIVE,
    GOOGLE_SHEETS,
    GoogleUnauthorized,
    calendar,
    drive,
    gmail,
    sheets,
)
from app.services.cache import TTLCache
from app.services.google.token_service import GoogleTokenService

logger = logging.getLogger(__name__)

_cache = TTLCache(ttl_seconds=settings.GOOGLE_CACHE_TTL_SECONDS)


class GoogleDataService:
    """Read-only access to a single user's Google data."""

    def __init__(
        self,
        db: Session,
        user_id: int,
        token_service: Optional[GoogleTokenService] = None,
    ):
        self.db = db
        self.user_id = user_id
        self.token_service = token_service or GoogleTokenService(db)

    # -----------------------------------------------------
    # Connection state
    # -----------------------------------------------------

    def connected_services(self) -> List[str]:
        return self.token_service.connected_services(self.user_id)

    # -----------------------------------------------------
    # Gmail
    # -----------------------------------------------------

    async def gmail_search(
        self,
        query: Optional[str] = None,
        max_results: int = 10,
    ) -> Dict[str, Any]:

        messages = await self._call(
            GMAIL,
            lambda token: gmail.search_messages(
                token,
                query=query,
                max_results=max_results,
            ),
            cache_key=("gmail_search", query, max_results),
        )

        return {"query": query, "count": len(messages), "messages": messages}

    async def gmail_message(self, message_id: str) -> Dict[str, Any]:

        return await self._call(
            GMAIL,
            lambda token: gmail.get_message(token, message_id),
            cache_key=("gmail_message", message_id),
        )

    # -----------------------------------------------------
    # Calendar
    # -----------------------------------------------------

    async def calendar_events(
        self,
        time_min: Optional[str] = None,
        time_max: Optional[str] = None,
        query: Optional[str] = None,
        max_results: int = 10,
        calendar_id: str = "primary",
    ) -> Dict[str, Any]:

        events = await self._call(
            GOOGLE_CALENDAR,
            lambda token: calendar.list_events(
                token,
                time_min=time_min,
                time_max=time_max,
                query=query,
                max_results=max_results,
                calendar_id=calendar_id,
            ),
            cache_key=(
                "calendar_events",
                time_min,
                time_max,
                query,
                max_results,
                calendar_id,
            ),
        )

        return {"count": len(events), "events": events}

    async def calendar_list(self) -> Dict[str, Any]:

        calendars = await self._call(
            GOOGLE_CALENDAR,
            calendar.list_calendars,
            cache_key=("calendar_list",),
        )

        return {"count": len(calendars), "calendars": calendars}

    # -----------------------------------------------------
    # Drive
    # -----------------------------------------------------

    async def drive_search(
        self,
        query: Optional[str] = None,
        mime_type: Optional[str] = None,
        max_results: int = 10,
    ) -> Dict[str, Any]:

        files = await self._call(
            GOOGLE_DRIVE,
            lambda token: drive.search_files(
                token,
                query=query,
                mime_type=mime_type,
                max_results=max_results,
            ),
            cache_key=("drive_search", query, mime_type, max_results),
        )

        return {"query": query, "count": len(files), "files": files}

    async def drive_read_file(self, file_id: str) -> Dict[str, Any]:

        return await self._call(
            GOOGLE_DRIVE,
            lambda token: drive.read_file_text(token, file_id),
            cache_key=("drive_read_file", file_id),
        )

    # -----------------------------------------------------
    # Sheets
    # -----------------------------------------------------

    async def sheets_list(
        self,
        query: Optional[str] = None,
        max_results: int = 10,
    ) -> Dict[str, Any]:

        spreadsheets = await self._call(
            GOOGLE_SHEETS,
            lambda token: sheets.list_spreadsheets(
                token,
                query=query,
                max_results=max_results,
            ),
            cache_key=("sheets_list", query, max_results),
        )

        return {
            "count": len(spreadsheets),
            "spreadsheets": spreadsheets,
        }

    async def sheets_metadata(
        self,
        spreadsheet_id: str,
    ) -> Dict[str, Any]:

        return await self._call(
            GOOGLE_SHEETS,
            lambda token: sheets.get_metadata(token, spreadsheet_id),
            cache_key=("sheets_metadata", spreadsheet_id),
        )

    async def sheets_values(
        self,
        spreadsheet_id: str,
        range_a1: Optional[str] = None,
        max_rows: Optional[int] = None,
    ) -> Dict[str, Any]:

        return await self._call(
            GOOGLE_SHEETS,
            lambda token: sheets.read_values(
                token,
                spreadsheet_id=spreadsheet_id,
                range_a1=range_a1,
                max_rows=max_rows,
            ),
            cache_key=(
                "sheets_values",
                spreadsheet_id,
                range_a1,
                max_rows,
            ),
        )

    # -----------------------------------------------------
    # Internals
    # -----------------------------------------------------

    async def _call(
        self,
        service_name: str,
        operation: Callable[[str], Any],
        cache_key: Optional[tuple] = None,
    ) -> Any:
        """Run a Google API call with caching and 401 recovery."""

        key = self._cache_key(service_name, cache_key)

        if key:
            cached = _cache.get(key)

            if cached is not None:
                return cached

        access_token = await self.token_service.get_access_token(
            self.user_id, service_name
        )

        try:
            result = await operation(access_token)
        except GoogleUnauthorized:
            logger.info(
                "Google returned 401, refreshing token "
                "(user=%s service=%s)",
                self.user_id,
                service_name,
            )
            access_token = await self.token_service.get_access_token(
                self.user_id,
                service_name,
                force_refresh=True,
            )
            result = await operation(access_token)

        if key:
            _cache.set(key, result)

        return result

    def _cache_key(
        self,
        service_name: str,
        parts: Optional[tuple],
    ) -> Optional[str]:

        if parts is None:
            return None

        digest = hashlib.sha256(
            json.dumps(parts, default=str, sort_keys=True).encode()
        ).hexdigest()

        return f"{self.user_id}:{service_name}:{digest}"

    def invalidate_cache(self) -> None:
        _cache.invalidate_prefix(f"{self.user_id}:")
