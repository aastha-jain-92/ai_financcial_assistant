"""LLM tool definitions backed by the user's Google account.

Only tools for services the user has actually connected are exposed,
so the model never promises data it cannot reach.
"""

from typing import Any, Dict, Iterable, List

from app.providers.google import (
    GMAIL,
    GOOGLE_CALENDAR,
    GOOGLE_DRIVE,
    GOOGLE_SHEETS,
    SERVICE_LABELS,
)
from app.services.google.google_service import GoogleDataService
from app.services.tools.base import ToolSpec


def build_google_tools(
    google_service: GoogleDataService,
    connected_services: Iterable[str],
) -> List[ToolSpec]:
    """Return the tool specs for the services the user has connected."""

    connected = set(connected_services)
    specs: List[ToolSpec] = []

    if GMAIL in connected:
        specs.extend(_gmail_tools(google_service))

    if GOOGLE_CALENDAR in connected:
        specs.extend(_calendar_tools(google_service))

    if GOOGLE_DRIVE in connected:
        specs.extend(_drive_tools(google_service))

    if GOOGLE_SHEETS in connected:
        specs.extend(_sheets_tools(google_service))

    return specs


def google_tools_prompt(connected_services: Iterable[str]) -> str:
    """System-prompt fragment describing the user's Google access."""

    connected = sorted(set(connected_services))

    if not connected:
        return (
            "GOOGLE WORKSPACE ACCESS\n"
            "The user has not connected any Google service. "
            "If a question needs their Gmail, Calendar, Drive or Sheets "
            "data, explain that and ask them to run /connect in Telegram. "
            "Never invent the contents of their Google account."
        )

    labels = ", ".join(
        SERVICE_LABELS.get(service, service) for service in connected
    )

    missing = [
        SERVICE_LABELS.get(service, service)
        for service in (
            GMAIL,
            GOOGLE_CALENDAR,
            GOOGLE_DRIVE,
            GOOGLE_SHEETS,
        )
        if service not in connected
    ]

    lines = [
        "GOOGLE WORKSPACE ACCESS",
        f"Connected services: {labels}.",
        "Use the matching tools whenever the question depends on the "
        "user's own email, calendar, files or spreadsheets "
        "(for example \"summarise my bank alerts\", \"what earnings "
        "calls do I have this week\", \"what is in my portfolio "
        "sheet\").",
        "Always base such answers on tool results only, cite the "
        "subject/file/event names you used, and never fabricate "
        "personal data.",
        "Search in small steps: find the messages/files first, then "
        "read only the ones you need.",
    ]

    if missing:
        lines.append(
            "Not connected: "
            + ", ".join(missing)
            + ". If one of those is needed, ask the user to run "
            "/connect."
        )

    return "\n".join(lines)


# ---------------------------------------------------------------
# Gmail
# ---------------------------------------------------------------


def _gmail_tools(service: GoogleDataService) -> List[ToolSpec]:

    async def search(arguments: Dict[str, Any]) -> Any:
        return await service.gmail_search(
            query=arguments.get("query"),
            max_results=arguments.get("max_results", 10),
        )

    async def read(arguments: Dict[str, Any]) -> Any:
        return await service.gmail_message(
            message_id=arguments["message_id"],
        )

    return [
        ToolSpec(
            name="gmail_search_messages",
            description=(
                "Search the user's Gmail inbox and return message "
                "metadata (sender, subject, date, snippet). Supports "
                "Gmail search syntax such as "
                "'from:hdfcbank.net newer_than:30d', "
                "'subject:statement has:attachment'."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "Gmail search query. Leave empty for the "
                            "most recent messages."
                        ),
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "How many messages to return (1-10).",
                    },
                },
            },
            handler=search,
        ),
        ToolSpec(
            name="gmail_read_message",
            description=(
                "Read the full body of one Gmail message, identified by "
                "the message_id returned by gmail_search_messages."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "message_id": {
                        "type": "string",
                        "description": "Gmail message id.",
                    },
                },
                "required": ["message_id"],
            },
            handler=read,
        ),
    ]


# ---------------------------------------------------------------
# Calendar
# ---------------------------------------------------------------


def _calendar_tools(service: GoogleDataService) -> List[ToolSpec]:

    async def events(arguments: Dict[str, Any]) -> Any:
        return await service.calendar_events(
            time_min=arguments.get("time_min"),
            time_max=arguments.get("time_max"),
            query=arguments.get("query"),
            max_results=arguments.get("max_results", 10),
            calendar_id=arguments.get("calendar_id", "primary"),
        )

    async def calendars(_: Dict[str, Any]) -> Any:
        return await service.calendar_list()

    return [
        ToolSpec(
            name="calendar_list_events",
            description=(
                "List the user's Google Calendar events in a time "
                "window (defaults to the next 30 days). Use it for "
                "questions about meetings, earnings calls or reminders."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "time_min": {
                        "type": "string",
                        "description": (
                            "Start of the window as an ISO-8601 UTC "
                            "timestamp, e.g. 2026-08-12T00:00:00Z."
                        ),
                    },
                    "time_max": {
                        "type": "string",
                        "description": (
                            "End of the window as an ISO-8601 UTC "
                            "timestamp."
                        ),
                    },
                    "query": {
                        "type": "string",
                        "description": "Free-text filter for events.",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "How many events to return (1-20).",
                    },
                    "calendar_id": {
                        "type": "string",
                        "description": (
                            "Calendar id; defaults to 'primary'."
                        ),
                    },
                },
            },
            handler=events,
        ),
        ToolSpec(
            name="calendar_list_calendars",
            description=(
                "List the calendars the user has access to, with their "
                "ids and time zones."
            ),
            parameters={"type": "object", "properties": {}},
            handler=calendars,
        ),
    ]


# ---------------------------------------------------------------
# Drive
# ---------------------------------------------------------------


def _drive_tools(service: GoogleDataService) -> List[ToolSpec]:

    async def search(arguments: Dict[str, Any]) -> Any:
        return await service.drive_search(
            query=arguments.get("query"),
            mime_type=arguments.get("mime_type"),
            max_results=arguments.get("max_results", 10),
        )

    async def read(arguments: Dict[str, Any]) -> Any:
        return await service.drive_read_file(
            file_id=arguments["file_id"],
        )

    return [
        ToolSpec(
            name="drive_search_files",
            description=(
                "Search the user's Google Drive by file name and "
                "content, newest first. Returns file ids to pass to "
                "drive_read_file."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "Words to look for in the file name or "
                            "contents, e.g. 'Q3 earnings report'."
                        ),
                    },
                    "mime_type": {
                        "type": "string",
                        "description": (
                            "Optional MIME type filter, e.g. "
                            "'application/vnd.google-apps.document' or "
                            "'application/pdf'."
                        ),
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "How many files to return (1-20).",
                    },
                },
            },
            handler=search,
        ),
        ToolSpec(
            name="drive_read_file",
            description=(
                "Read the text of a Drive file (Google Docs, Sheets, "
                "Slides or plain-text files). Content is truncated for "
                "long documents."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "file_id": {
                        "type": "string",
                        "description": (
                            "Drive file id from drive_search_files."
                        ),
                    },
                },
                "required": ["file_id"],
            },
            handler=read,
        ),
    ]


# ---------------------------------------------------------------
# Sheets
# ---------------------------------------------------------------


def _sheets_tools(service: GoogleDataService) -> List[ToolSpec]:

    async def list_sheets(arguments: Dict[str, Any]) -> Any:
        return await service.sheets_list(
            query=arguments.get("query"),
            max_results=arguments.get("max_results", 10),
        )

    async def metadata(arguments: Dict[str, Any]) -> Any:
        return await service.sheets_metadata(
            spreadsheet_id=arguments["spreadsheet_id"],
        )

    async def values(arguments: Dict[str, Any]) -> Any:
        return await service.sheets_values(
            spreadsheet_id=arguments["spreadsheet_id"],
            range_a1=arguments.get("range"),
            max_rows=arguments.get("max_rows"),
        )

    return [
        ToolSpec(
            name="sheets_find_spreadsheets",
            description=(
                "Find the user's Google Sheets by name, e.g. "
                "'portfolio', 'budget 2026'. Returns spreadsheet ids."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Words in the spreadsheet name.",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "How many results (1-20).",
                    },
                },
            },
            handler=list_sheets,
        ),
        ToolSpec(
            name="sheets_get_metadata",
            description=(
                "List the tabs (and their sizes) of one spreadsheet "
                "before reading a range from it."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "spreadsheet_id": {
                        "type": "string",
                        "description": "Google Sheets spreadsheet id.",
                    },
                },
                "required": ["spreadsheet_id"],
            },
            handler=metadata,
        ),
        ToolSpec(
            name="sheets_read_values",
            description=(
                "Read cell values from a spreadsheet range in A1 "
                "notation, e.g. 'Portfolio!A1:F50'. Omit the range to "
                "read the first tab. Use the values to compute totals "
                "or answer questions about the user's own data."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "spreadsheet_id": {
                        "type": "string",
                        "description": "Google Sheets spreadsheet id.",
                    },
                    "range": {
                        "type": "string",
                        "description": "A1 notation range.",
                    },
                    "max_rows": {
                        "type": "integer",
                        "description": "Maximum rows to return (1-100).",
                    },
                },
                "required": ["spreadsheet_id"],
            },
            handler=values,
        ),
    ]
