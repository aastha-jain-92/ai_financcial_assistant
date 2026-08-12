import logging

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from app.database.database import SessionLocal

from app.repositories.user_repository import (
    SQLAlchemyUserRepository,
)

from app.services.ai_services import AIService
from app.services.audio_service import AudioService
import base64


logger = logging.getLogger(__name__)


async def chat_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """ Handle normal chat messages after onboarding. """
    if not update.message:
        return

    user_message = ""
    base64_image = None

    if update.message.text:
        user_message = update.message.text.strip()
    elif update.message.voice:
        # Download voice note and transcribe
        voice_file = await update.message.voice.get_file()
        voice_bytes = await voice_file.download_as_bytearray()
        
        audio_service = AudioService()
        try:
            transcribed_text = await audio_service.transcribe(bytes(voice_bytes), filename="voice.ogg")
            user_message = transcribed_text.strip()
        except Exception as e:
            logger.error(f"Voice transcription failed: {e}")
            await update.message.reply_text("Sorry, I couldn't transcribe your voice message.")
            return
            
    elif update.message.photo:
        # Get highest resolution photo
        photo = update.message.photo[-1]
        photo_file = await photo.get_file()
        photo_bytes = await photo_file.download_as_bytearray()
        
        base64_image = base64.b64encode(photo_bytes).decode('utf-8')
        user_message = update.message.caption.strip() if update.message.caption else "Please describe this image."
        
    if not user_message and not base64_image:
        await update.message.reply_text("Please enter a valid message, voice note, or image.")
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
        response = await ai_service.chat(
            user_id=user.id, 
            message=user_message, 
            history_limit=10, 
            base64_image=base64_image
        )
        # --------------------------------------------- # Send response # --------------------------------------------- #
        await update.message.reply_text( response )
    except Exception:
        logger.exception( "Error processing chat message" )
        db.rollback()
        await update.message.reply_text( "Sorry, something went wrong while " "processing your request." )
    finally:
        db.close()