"""Google Calendar read-only API calls."""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from app.config import settings

from .constants import CALENDAR_API
from .http import request_json


async def list_events(
    access_token: str,
    time_min: Optional[str] = None,
    time_max: Optional[str] = None,
    query: Optional[str] = None,
    max_results: int = 10,
    calendar_id: str = "primary",
) -> List[Dict[str, Any]]:
    """Return upcoming (or filtered) events for a calendar."""

    now = datetime.now(timezone.utc)

    params: Dict[str, Any] = {
        "timeMin": _to_rfc3339(time_min, now),
        "timeMax": _to_rfc3339(time_max, now + timedelta(days=30)),
        "maxResults": _clamp(max_results, settings.CALENDAR_MAX_EVENTS),
        "singleEvents": "true",
        "orderBy": "startTime",
    }

    if query:
        params["q"] = query

    payload = await request_json(
        "GET",
        f"{CALENDAR_API}/calendars/{calendar_id}/events",
        access_token=access_token,
        params=params,
    )

    return [
        _map_event(item)
        for item in (payload or {}).get("items", [])
    ]


async def list_calendars(access_token: str) -> List[Dict[str, Any]]:

    payload = await request_json(
        "GET",
        f"{CALENDAR_API}/users/me/calendarList",
        access_token=access_token,
        params={"maxResults": 50},
    )

    return [
        {
            "id": item.get("id"),
            "summary": item.get("summary"),
            "primary": bool(item.get("primary")),
            "time_zone": item.get("timeZone"),
        }
        for item in (payload or {}).get("items", [])
    ]


def _map_event(item: Dict[str, Any]) -> Dict[str, Any]:

    start = item.get("start") or {}
    end = item.get("end") or {}

    return {
        "id": item.get("id"),
        "summary": item.get("summary"),
        "description": (item.get("description") or "")[:500],
        "location": item.get("location"),
        "start": start.get("dateTime") or start.get("date"),
        "end": end.get("dateTime") or end.get("date"),
        "all_day": "date" in start,
        "status": item.get("status"),
        "organizer": (item.get("organizer") or {}).get("email"),
        "attendees": [
            attendee.get("email")
            for attendee in (item.get("attendees") or [])
            if attendee.get("email")
        ][:10],
        "meeting_link": item.get("hangoutLink"),
        "html_link": item.get("htmlLink"),
    }


def _to_rfc3339(value: Optional[str], fallback: datetime) -> str:

    if not value:
        return fallback.isoformat().replace("+00:00", "Z")

    text = value.strip()

    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return fallback.isoformat().replace("+00:00", "Z")

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc).isoformat().replace(
        "+00:00", "Z"
    )


def _clamp(value: Any, maximum: int) -> int:

    try:
        value = int(value)
    except (TypeError, ValueError):
        return maximum

    return max(1, min(value, maximum))
