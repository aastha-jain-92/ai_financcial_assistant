# app/telegram/handlers/onboarding.py
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

from app.bot.handlers.integrations import (
    build_authorization_link,
    connected_services_for,
    disconnect_service,
)
from app.providers.google import SERVICE_LABELS, normalize_service
from app.services.onboarding_service import OnboardingService
from app.database.database import SessionLocal

import logging

logger = logging.getLogger(__name__)


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

    if data.startswith("integration_disconnect_"):
        service = data.replace("integration_disconnect_", "")

        message = await disconnect_service(
            telegram_id=update.effective_user.id,
            service_name=service,
        )

        await query.edit_message_text(message)
        return None

    if data.startswith("integration_connect_"):
        service = normalize_service(
            data.replace("integration_connect_", "")
        )
        label = SERVICE_LABELS.get(service, service)

        oauth_url, error = build_authorization_link(
            telegram_id=update.effective_user.id,
            service_name=service,
            chat_id=update.effective_chat.id,
        )

        if error:
            await query.edit_message_text(f"❌ {error}")
            return None

        await query.edit_message_text(
            f"🔗 *Connect {label}*\n\n"
            "Open the link below, approve read-only access, then come "
            "back here — I'll confirm as soon as it's linked.\n\n"
            f"{oauth_url}\n\n"
            "_The link is single-use and expires in a few minutes._",
            parse_mode="Markdown",
            disable_web_page_preview=True,
        )

        await query.message.reply_text(
            "Would you like to connect anything else?",
            reply_markup=integrations_keyboard(
                connected=connected_services_for(
                    update.effective_user.id
                )
            ),
        )

    return None


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
