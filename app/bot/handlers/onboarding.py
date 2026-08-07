# app/telegram/handlers/onboarding.py
from app.database.database import SessionLocal
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
    BRIEFING
)

from app.bot.keyboards import (
    role_keyboard,
    market_keyboard
)

from app.repositories.user_repository import SQLAlchemyUserRepository
from app.services.onboarding_service import OnboardingService
from app.database.database import SessionLocal

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
        "What best describes you?",
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
        "or type Skip"
    )

    return COMPANIES



async def companies(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    context.user_data["companies"] = update.message.text

    await update.message.reply_text(
        "Which market do you follow?",
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
        "Market News,Earnings"
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
        "or Skip"
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


    await update.message.reply_text(
        "✅ Your onboarding is complete!\n\n"
        "You can now ask me anything about finance."
    )

    return ConversationHandler.END


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