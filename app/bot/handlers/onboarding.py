# app/telegram/handlers/onboarding.py
from app.database.database import SessionLocal
from urllib.parse import urlencode
import os
import secrets
from telegram import Update
from telegram.ext import (
    ContextTypes,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    filters
)
from app.core.dependency import get_onboarding_service

from app.bot.states import (
    ROLE,
    COMPANIES,
    MARKET,
    PREFERENCES,
    BRIEFING,
    INTEGRATIONS,
)

from app.bot.keyboards import (
    role_keyboard,
    market_keyboard,
    integrations_keyboard,
)

from app.repositories.user_repository import SQLAlchemyUserRepository
from app.repositories.user_integration_repository import (
    SQLAlchemyUserIntegrationRepository,
)
from app.services.onboarding_service import OnboardingService
from app.database.database import SessionLocal

import logging

logger = logging.getLogger(__name__)


# ---------------------------------------------------------
# Service display names
# ---------------------------------------------------------

SERVICE_LABELS = {
    "gmail": "📧 Gmail",
    "google_calendar": "📅 Google Calendar",
    "google_drive": "📁 Google Drive",
    "google_sheets": "📊 Google Sheets",
}


def normalize_role(value: str | None):

    if not value:
        return ""

    mapping = {
        "investor": "Investor",
        "analyst": "Analyst",
        "founder": "Founder",
        "student": "Student",
        "finance professional": "Finance Professional",
        "skip": "Skip",
    }

    return mapping.get(
        value.strip().lower(),
        value.strip()
    )


async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        "👋 Welcome to AI Financial Assistant\n\n"
        "What best describes you?\n\n e.g  Investor,Analyst,Founder,Student,Financial Professional \n\n You can skip this question also.",
        reply_markup=role_keyboard()
    )

    return ROLE



async def role(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    context.user_data["role"] = normalize_role(
        update.message.text
    )

    await update.message.reply_text(
        "Which companies do you follow?\n\n"
        "Example:\n"
        "Apple,Tesla,Nvidia\n\n"
        "or You can skip this question also."
    )

    return COMPANIES



async def companies(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    context.user_data["companies"] = update.message.text

    await update.message.reply_text(
        "Which market do you follow?\n\n e.g Indian market, US market \n\n You can skip this question also.",
        reply_markup=market_keyboard()
    )

    return MARKET



async def market(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    context.user_data["market"] = update.message.text

    await update.message.reply_text(
        "What updates do you want?\n\n"
        "Example:\n"
        "Market News,Earnings \n\n You can skip this question also."
    )

    return PREFERENCES



async def preferences(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    context.user_data["preferences"] = update.message.text

    await update.message.reply_text(
        "At what time should I send your Daily Briefing?\n\n"
        "Example:\n"
        "08:00 AM\n\n"
        "or You can skip this question also."
    )

    return BRIEFING



async def briefing(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    context.user_data["briefing_time"] = update.message.text

    db = SessionLocal()

    try:

        onboarding_service = OnboardingService(db)

        onboarding_service.complete_onboarding(
            telegram_id=update.effective_user.id,
            full_name=update.effective_user.full_name,
            role=context.user_data["role"],
            companies=context.user_data["companies"],
            market=context.user_data["market"],
            preferences=context.user_data["preferences"],
            briefing_time=context.user_data["briefing_time"],
        )

        db.commit()


    except Exception as e:

        db.rollback()
        raise e


    finally:

        db.close()

    # ---------------------------------------------------------
    # Transition to integrations step
    # ---------------------------------------------------------

    context.user_data.setdefault("connected_services", [])

    await update.message.reply_text(
        "🔗 *Would you like to connect any Google services?*\n\n"
        "Connecting your accounts helps me:\n"
        "• Read financial reports from your Drive\n"
        "• Check your calendar for earnings calls\n"
        "• Send summaries to your Gmail\n"
        "• Export data to Google Sheets\n\n"
        "You can connect them now or skip and do it later "
        "with the /connect command.",
        parse_mode="Markdown",
        reply_markup=integrations_keyboard(),
    )

    return ConversationHandler.END


async def integrations_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    """
    Handle inline-button presses on the integrations keyboard.
    """

    query = update.callback_query
    await query.answer()

    data = query.data

    # ---------------------------------------------------------
    # Skip All
    # ---------------------------------------------------------

    if data == "integration_skip":
        await query.edit_message_text(
            "✅ Your onboarding is complete!\n\n"
            "You can now ask me anything about finance.\n"
            "Use /connect anytime to link your Google services."
        )
        return ConversationHandler.END

    # ---------------------------------------------------------
    # Already connected — just acknowledge
    # ---------------------------------------------------------

    if data.startswith("integration_connected_"):
        service = data.replace("integration_connected_", "")
        label = SERVICE_LABELS.get(service, service)
        await query.answer(
            text=f"{label} is already connected!",
            show_alert=True,
        )
        return None

    # ---------------------------------------------------------
    # Connect a service
    # ---------------------------------------------------------

    if data.startswith("integration_connect_"):
        service = data.replace("integration_connect_", "")
        label = SERVICE_LABELS.get(service, service)

        # Record the intent in user_data
        connected = context.user_data.setdefault(
            "connected_services", []
        )

        if service not in connected:
            connected.append(service)

        # Persist to database
        db = SessionLocal()
        try:
            user_repo = SQLAlchemyUserRepository(db)
            user = user_repo.get_by_telegram_id(
                update.effective_user.id
            )

            if user:
                integration_repo = (
                    SQLAlchemyUserIntegrationRepository(db)
                )
                integration_repo.create_or_update(
                    user_id=user.id,
                    service_name=service,
                    is_connected=False,  # placeholder until real OAuth
                )
                db.commit()
        except Exception:
            db.rollback()
            logger.exception("Failed to save integration intent")
        finally:
            db.close()

        # Send placeholder OAuth link
        


        client_id = os.getenv("GOOGLE_CLIENT_ID")
        redirect_uri = os.getenv("GOOGLE_REDIRECT_URI")

        if not client_id or not redirect_uri:
            await query.edit_message_text(
            "❌ Google OAuth is not configured correctly.\n\n"
            "Check GOOGLE_CLIENT_ID and GOOGLE_REDIRECT_URI in your .env file."
        )
            return

        scopes = {
        "gmail": [
            "openid",
            "https://www.googleapis.com/auth/userinfo.email",
            "https://www.googleapis.com/auth/gmail.readonly",
        ],

        "google_sheets": [
            "openid",
            "https://www.googleapis.com/auth/userinfo.email",
            "https://www.googleapis.com/auth/spreadsheets",
        ],

        "google_drive": [
            "openid",
            "https://www.googleapis.com/auth/userinfo.email",
            "https://www.googleapis.com/auth/drive.readonly",
        ],

        "google_calendar": [
            "openid",
            "https://www.googleapis.com/auth/userinfo.email",
            "https://www.googleapis.com/auth/calendar.readonly",
        ],
    
        }

    # Generate a unique state value
    state = secrets.token_urlsafe(32)

    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(scopes[service]),
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }

    oauth_url = (
        "https://accounts.google.com/o/oauth2/v2/auth?"
        + urlencode(params)
    )

    logger.info("Google OAuth URL: %s", oauth_url)

    await query.edit_message_text(
        f"🔗 Connect {label}:\n\n"
        f"{oauth_url}",
    )

    await query.message.reply_text(
    "Would you like to connect anything else?",
    reply_markup=integrations_keyboard(
        connected=connected
        ),
    )
    return


onboarding_handler = ConversationHandler(

    entry_points=[
        CommandHandler(
            "start",
            start
        )
    ],

    states={

        ROLE: [
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                role
            )
        ],

        COMPANIES: [
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                companies
            )
        ],

        MARKET: [
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                market
            )
        ],

        PREFERENCES: [
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                preferences
            )
        ],

        BRIEFING: [
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                briefing
            )
        ],
    },

    fallbacks=[]
)

service, db = get_onboarding_service()
