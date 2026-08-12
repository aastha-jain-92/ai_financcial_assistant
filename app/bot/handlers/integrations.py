"""Telegram handlers for connecting/disconnecting Google services.

`/connect`  -> shows the integrations keyboard
`/disconnect` -> revokes a connected service

Each connect button mints a single-use OAuth `state` row bound to the
Telegram user and chat, so the callback in `app.api.auth` knows exactly
who came back from Google.
"""

import logging
from typing import List, Optional, Tuple

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.ext import ContextTypes

from app.bot.keyboards import integrations_keyboard
from app.database.database import SessionLocal
from app.providers.google import (
    SERVICE_LABELS,
    SUPPORTED_SERVICES,
    GoogleError,
    GoogleNotConfigured,
    GoogleOAuthClient,
    normalize_service,
)
from app.repositories.oauth_state_repository import (
    SQLAlchemyOAuthStateRepository,
)
from app.repositories.user_repository import SQLAlchemyUserRepository
from app.services.google.token_service import GoogleTokenService

logger = logging.getLogger(__name__)

NOT_ONBOARDED = (
    "I don't have your profile yet. Send /start first, then try again."
)


# ---------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------


def connected_services_for(telegram_id: int) -> List[str]:
    """Services the given Telegram user has actually authorized."""

    db = SessionLocal()
    try:
        user = SQLAlchemyUserRepository(db).get_by_telegram_id(
            telegram_id
        )

        if user is None:
            return []

        return GoogleTokenService(db).connected_services(user.id)

    except Exception:
        logger.exception("Could not load connected Google services")
        return []
    finally:
        db.close()


def build_authorization_link(
    telegram_id: int,
    service_name: str,
    chat_id: Optional[int],
) -> Tuple[Optional[str], Optional[str]]:
    """Return `(url, error_message)` for a connect button press."""

    service = normalize_service(service_name)

    if service not in SUPPORTED_SERVICES:
        return None, f"Unknown Google service: {service_name}"

    db = SessionLocal()
    try:
        user = SQLAlchemyUserRepository(db).get_by_telegram_id(
            telegram_id
        )

        if user is None:
            return None, NOT_ONBOARDED

        oauth_client = GoogleOAuthClient()

        state = SQLAlchemyOAuthStateRepository(db).create(
            user_id=user.id,
            service_name=service,
            telegram_chat_id=chat_id,
        )

        url = oauth_client.build_authorization_url(
            service_name=service,
            state=state.state,
        )

        db.commit()

        return url, None

    except GoogleNotConfigured:
        db.rollback()
        logger.error("Google OAuth credentials are not configured")
        return None, (
            "Google sign-in isn't configured on the server yet. "
            "Please contact the administrator."
        )

    except GoogleError as exc:
        db.rollback()
        logger.warning("Could not build Google auth URL: %s", exc)
        return None, "Could not start the Google connection."

    except Exception:
        db.rollback()
        logger.exception("Could not build Google auth URL")
        return None, "Could not start the Google connection."

    finally:
        db.close()


async def disconnect_service(
    telegram_id: int,
    service_name: str,
) -> str:
    """Revoke a grant and return the message to show the user."""

    service = normalize_service(service_name)
    label = SERVICE_LABELS.get(service, service)

    db = SessionLocal()
    try:
        user = SQLAlchemyUserRepository(db).get_by_telegram_id(
            telegram_id
        )

        if user is None:
            return NOT_ONBOARDED

        removed = await GoogleTokenService(db).disconnect(
            user_id=user.id,
            service_name=service,
        )

        if not removed:
            return f"{label} wasn't connected."

        return f"🔌 {label} has been disconnected."

    except Exception:
        db.rollback()
        logger.exception("Failed to disconnect %s", service)
        return "Something went wrong while disconnecting. Try again."
    finally:
        db.close()


# ---------------------------------------------------------
# Commands
# ---------------------------------------------------------


async def connect_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    connected = connected_services_for(update.effective_user.id)

    await update.message.reply_text(
        "🔗 *Connect your Google services*\n\n"
        "I can only read data from the services you connect, and you "
        "can disconnect any of them at any time with /disconnect.",
        parse_mode="Markdown",
        reply_markup=integrations_keyboard(connected=connected),
    )


async def disconnect_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    connected = connected_services_for(update.effective_user.id)

    if not connected:
        await update.message.reply_text(
            "You don't have any Google services connected. "
            "Use /connect to link one."
        )
        return

    buttons = [
        [
            InlineKeyboardButton(
                f"🔌 Disconnect {SERVICE_LABELS.get(service, service)}",
                callback_data=f"integration_disconnect_{service}",
            )
        ]
        for service in connected
    ]

    await update.message.reply_text(
        "Which service should I disconnect?",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
