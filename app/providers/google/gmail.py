"""Gmail read-only API calls, mapped to compact LLM-friendly dicts."""

import asyncio
import base64
import binascii
from typing import Any, Dict, List, Optional

from app.config import settings

from .constants import GMAIL_API
from .http import request_json

_WANTED_HEADERS = ("From", "To", "Subject", "Date")


async def search_messages(
    access_token: str,
    query: Optional[str] = None,
    max_results: int = 10,
    include_spam_trash: bool = False,
) -> List[Dict[str, Any]]:
    """Return metadata for the messages matching a Gmail search query."""

    max_results = _clamp(max_results, settings.GMAIL_MAX_MESSAGES)

    params: Dict[str, Any] = {
        "maxResults": max_results,
        "includeSpamTrash": str(include_spam_trash).lower(),
    }

    if query:
        params["q"] = query

    listing = await request_json(
        "GET",
        f"{GMAIL_API}/users/me/messages",
        access_token=access_token,
        params=params,
    )

    message_ids = [
        item["id"]
        for item in (listing or {}).get("messages", [])
        if item.get("id")
    ]

    if not message_ids:
        return []

    messages = await asyncio.gather(
        *[
            _get_message_metadata(access_token, message_id)
            for message_id in message_ids
        ],
        return_exceptions=True,
    )

    return [
        message
        for message in messages
        if isinstance(message, dict)
    ]


async def get_message(
    access_token: str,
    message_id: str,
) -> Dict[str, Any]:
    """Return a single message including its plain-text body."""

    payload = await request_json(
        "GET",
        f"{GMAIL_API}/users/me/messages/{message_id}",
        access_token=access_token,
        params={"format": "full"},
    )

    message = _map_message(payload)
    message["body"] = _extract_body(payload.get("payload") or {})

    return message


async def _get_message_metadata(
    access_token: str,
    message_id: str,
) -> Dict[str, Any]:

    payload = await request_json(
        "GET",
        f"{GMAIL_API}/users/me/messages/{message_id}",
        access_token=access_token,
        params=[
            ("format", "metadata"),
            *[
                ("metadataHeaders", header)
                for header in _WANTED_HEADERS
            ],
        ],
    )

    return _map_message(payload)


def _map_message(payload: Dict[str, Any]) -> Dict[str, Any]:

    headers = {
        header.get("name", "").lower(): header.get("value", "")
        for header in (payload.get("payload") or {}).get("headers", [])
    }

    return {
        "id": payload.get("id"),
        "thread_id": payload.get("threadId"),
        "from": headers.get("from"),
        "to": headers.get("to"),
        "subject": headers.get("subject"),
        "date": headers.get("date"),
        "snippet": payload.get("snippet"),
        "labels": payload.get("labelIds", []),
    }


def _extract_body(part: Dict[str, Any]) -> str:
    """Depth-first search for the best text representation of a message."""

    collected: List[str] = []
    _collect_text(part, collected, prefer_html=False)

    if not collected:
        _collect_text(part, collected, prefer_html=True)

    body = "\n".join(collected).strip()

    return body[: settings.GMAIL_MAX_BODY_CHARS]


def _collect_text(
    part: Dict[str, Any],
    collected: List[str],
    prefer_html: bool,
) -> None:

    mime_type = part.get("mimeType", "")
    wanted = "text/html" if prefer_html else "text/plain"

    if mime_type == wanted:
        text = _decode(part.get("body", {}).get("data"))

        if text:
            collected.append(
                _strip_html(text) if prefer_html else text
            )

    for child in part.get("parts", []) or []:
        _collect_text(child, collected, prefer_html)


def _decode(data: Optional[str]) -> str:

    if not data:
        return ""

    try:
        return base64.urlsafe_b64decode(data).decode(
            "utf-8", errors="replace"
        )
    except (binascii.Error, ValueError):
        return ""


def _strip_html(html: str) -> str:

    output: List[str] = []
    depth = 0

    for char in html:
        if char == "<":
            depth += 1
        elif char == ">":
            depth = max(0, depth - 1)
        elif depth == 0:
            output.append(char)

    return " ".join("".join(output).split())


def _clamp(value: Any, maximum: int) -> int:

    try:
        value = int(value)
    except (TypeError, ValueError):
        return maximum

    return max(1, min(value, maximum))
