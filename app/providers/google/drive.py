"""Google Drive read-only API calls."""

from typing import Any, Dict, List, Optional

from app.config import settings

from .constants import DRIVE_API
from .exceptions import GoogleAPIError
from .http import request_json

GOOGLE_DOC = "application/vnd.google-apps.document"
GOOGLE_SHEET = "application/vnd.google-apps.spreadsheet"
GOOGLE_SLIDE = "application/vnd.google-apps.presentation"

EXPORT_MIME_TYPES = {
    GOOGLE_DOC: "text/plain",
    GOOGLE_SHEET: "text/csv",
    GOOGLE_SLIDE: "text/plain",
}

READABLE_PREFIXES = ("text/", "application/json")

_FILE_FIELDS = (
    "id,name,mimeType,modifiedTime,size,owners(displayName),"
    "webViewLink,iconLink"
)


async def search_files(
    access_token: str,
    query: Optional[str] = None,
    mime_type: Optional[str] = None,
    max_results: int = 10,
) -> List[Dict[str, Any]]:
    """Search Drive files by free-text name/content query."""

    clauses = ["trashed = false"]

    if query:
        clauses.append(f"fullText contains '{_escape(query)}'")

    if mime_type:
        clauses.append(f"mimeType = '{_escape(mime_type)}'")

    payload = await request_json(
        "GET",
        f"{DRIVE_API}/files",
        access_token=access_token,
        params={
            "q": " and ".join(clauses),
            "pageSize": _clamp(max_results, settings.DRIVE_MAX_FILES),
            "orderBy": "modifiedTime desc",
            "fields": f"files({_FILE_FIELDS})",
            "supportsAllDrives": "true",
            "includeItemsFromAllDrives": "true",
        },
    )

    return [
        _map_file(item)
        for item in (payload or {}).get("files", [])
    ]


async def get_file_metadata(
    access_token: str,
    file_id: str,
) -> Dict[str, Any]:

    payload = await request_json(
        "GET",
        f"{DRIVE_API}/files/{file_id}",
        access_token=access_token,
        params={
            "fields": _FILE_FIELDS,
            "supportsAllDrives": "true",
        },
    )

    return _map_file(payload or {})


async def read_file_text(
    access_token: str,
    file_id: str,
) -> Dict[str, Any]:
    """Return the text content of a Drive file (exported when needed)."""

    metadata = await get_file_metadata(access_token, file_id)
    mime_type = metadata.get("mime_type") or ""

    export_mime = EXPORT_MIME_TYPES.get(mime_type)

    if export_mime:
        content = await request_json(
            "GET",
            f"{DRIVE_API}/files/{file_id}/export",
            access_token=access_token,
            params={"mimeType": export_mime},
            expect_json=False,
        )
    elif mime_type.startswith(READABLE_PREFIXES):
        content = await request_json(
            "GET",
            f"{DRIVE_API}/files/{file_id}",
            access_token=access_token,
            params={"alt": "media", "supportsAllDrives": "true"},
            expect_json=False,
        )
    else:
        raise GoogleAPIError(
            415,
            f"File type '{mime_type}' cannot be read as text. "
            "Only Google Docs/Sheets/Slides and text files are supported.",
        )

    text = str(content or "")
    truncated = len(text) > settings.DRIVE_MAX_FILE_CHARS

    return {
        **metadata,
        "content": text[: settings.DRIVE_MAX_FILE_CHARS],
        "truncated": truncated,
    }


def _map_file(item: Dict[str, Any]) -> Dict[str, Any]:

    owners = item.get("owners") or []

    return {
        "id": item.get("id"),
        "name": item.get("name"),
        "mime_type": item.get("mimeType"),
        "modified_at": item.get("modifiedTime"),
        "size_bytes": item.get("size"),
        "owner": owners[0].get("displayName") if owners else None,
        "link": item.get("webViewLink"),
    }


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def _clamp(value: Any, maximum: int) -> int:

    try:
        value = int(value)
    except (TypeError, ValueError):
        return maximum

    return max(1, min(value, maximum))
