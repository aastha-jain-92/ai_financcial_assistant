import os
from dotenv import load_dotenv

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hello 👋\n\nWelcome to AI Financial Assistant!"
    )


application = Application.builder().token(TOKEN).build()

application.add_handler(CommandHandler("start", start))

if __name__ == "__main__":
    application.run_polling()