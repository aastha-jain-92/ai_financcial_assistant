"""Google Sheets read-only API calls."""

from typing import Any, Dict, List, Optional

from app.config import settings

from .constants import SHEETS_API
from .http import request_json
from . import drive


async def list_spreadsheets(
    access_token: str,
    query: Optional[str] = None,
    max_results: int = 10,
) -> List[Dict[str, Any]]:
    """Find the user's spreadsheets (uses the Drive API)."""

    return await drive.search_files(
        access_token=access_token,
        query=query,
        mime_type=drive.GOOGLE_SHEET,
        max_results=max_results,
    )


async def get_metadata(
    access_token: str,
    spreadsheet_id: str,
) -> Dict[str, Any]:
    """Return the title and tab layout of a spreadsheet."""

    payload = await request_json(
        "GET",
        f"{SHEETS_API}/{spreadsheet_id}",
        access_token=access_token,
        params={
            "fields": (
                "spreadsheetId,properties(title),"
                "sheets(properties(title,sheetId,gridProperties))"
            ),
        },
    )

    payload = payload or {}

    return {
        "spreadsheet_id": payload.get("spreadsheetId", spreadsheet_id),
        "title": (payload.get("properties") or {}).get("title"),
        "sheets": [
            {
                "title": (sheet.get("properties") or {}).get("title"),
                "sheet_id": (sheet.get("properties") or {}).get("sheetId"),
                "rows": (
                    (sheet.get("properties") or {})
                    .get("gridProperties", {})
                    .get("rowCount")
                ),
                "columns": (
                    (sheet.get("properties") or {})
                    .get("gridProperties", {})
                    .get("columnCount")
                ),
            }
            for sheet in payload.get("sheets", [])
        ],
    }


async def read_values(
    access_token: str,
    spreadsheet_id: str,
    range_a1: Optional[str] = None,
    max_rows: Optional[int] = None,
) -> Dict[str, Any]:
    """Read a range of cells; defaults to the first tab of the sheet."""

    if not range_a1:
        metadata = await get_metadata(access_token, spreadsheet_id)
        sheets = metadata.get("sheets") or []
        first_tab = sheets[0]["title"] if sheets else "Sheet1"
        range_a1 = f"{first_tab}"

    payload = await request_json(
        "GET",
        f"{SHEETS_API}/{spreadsheet_id}/values/{range_a1}",
        access_token=access_token,
        params={
            "majorDimension": "ROWS",
            "valueRenderOption": "UNFORMATTED_VALUE",
            "dateTimeRenderOption": "FORMATTED_STRING",
        },
    )

    values = (payload or {}).get("values", [])
    limit = _clamp(
        max_rows if max_rows is not None else settings.SHEETS_MAX_ROWS,
        settings.SHEETS_MAX_ROWS,
    )

    return {
        "spreadsheet_id": spreadsheet_id,
        "range": (payload or {}).get("range", range_a1),
        "row_count": len(values),
        "truncated": len(values) > limit,
        "values": values[:limit],
    }


def _clamp(value: Any, maximum: int) -> int:

    try:
        value = int(value)
    except (TypeError, ValueError):
        return maximum

    return max(1, min(value, maximum))
