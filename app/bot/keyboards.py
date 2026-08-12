# app/telegram/keyboards.py

from telegram import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)


def role_keyboard():

    keyboard = [
        [KeyboardButton("Investor")],
        [KeyboardButton("Analyst")],
        [KeyboardButton("Founder")],
        [KeyboardButton("Student")],
        [KeyboardButton("Finance Professional")],
        [KeyboardButton("Skip")]
    ]

    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True
    )


def market_keyboard():

    keyboard = [
        ["US Market"],
        ["Indian Market"],
        ["Global"],
        ["Skip"]
    ]

    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True
    )


def integrations_keyboard(connected=None):
    """
    Inline keyboard for Google service connections.

    connected: list of already-connected service names,
    used to show ✅ instead of the connect button.
    """

    if connected is None:
        connected = []

    services = [
        ("gmail", "📧 Gmail"),
        ("google_calendar", "📅 Google Calendar"),
        ("google_drive", "📁 Google Drive"),
        ("google_sheets", "📊 Google Sheets"),
    ]

    buttons = []
    for service_key, label in services:
        if service_key in connected:
            buttons.append(
                [InlineKeyboardButton(
                    f"✅ {label} (Connected)",
                    callback_data=f"integration_connected_{service_key}",
                )]
            )
        else:
            buttons.append(
                [InlineKeyboardButton(
                    f"🔗 Connect {label}",
                    callback_data=f"integration_connect_{service_key}",
                )]
            )

    buttons.append(
        [InlineKeyboardButton(
            "⏭️ Skip All / Connect Later",
            callback_data="integration_skip",
        )]
    )

    return InlineKeyboardMarkup(buttons)