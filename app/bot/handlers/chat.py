import logging

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from app.database.database import SessionLocal

from app.repositories.user_repository import (
    SQLAlchemyUserRepository,
)

from app.services.ai_services import AIService


logger = logging.getLogger(__name__)


async def chat_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """ Handle normal chat messages after onboarding. """
    if not update.message:
        return

    user_message = update.message.text

    if not user_message:
        return

    user_message = user_message.strip()

    if not user_message:
        await update.message.reply_text(
            "Please enter a valid message."
        )
        return

    db = SessionLocal()

    try:
        # --------------------------------------------- # Find Telegram user # ---------------------------------------------
        user_repository = (SQLAlchemyUserRepository(db))
        user = (user_repository.get_by_telegram_id(update.effective_user.id))
        if not user:
            await update.message.reply_text("Please complete onboarding first " "using /start.")
            return

        # ---------------------------------------------
        # Show typing indicator
        # ---------------------------------------------

        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id,
            action=ChatAction.TYPING,
        )

        # --------------------------------------------- # AI Service # --------------------------------------------- #
        ai_service = AIService(db)
        response = ai_service.chat( user_id=user.id, message=user_message, history_limit=10, )
        # --------------------------------------------- # Send response # --------------------------------------------- #
        await update.message.reply_text( response )
    except Exception:
        logger.exception( "Error processing chat message" )
        db.rollback()
        await update.message.reply_text( "Sorry, something went wrong while " "processing your request." )
    finally:
        db.close()