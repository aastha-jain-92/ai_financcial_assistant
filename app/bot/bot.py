# app/telegram/bot.py

import os
import sys
import atexit

from pathlib import Path
from dotenv import load_dotenv

from telegram.ext import Application, MessageHandler, filters, CommandHandler, CallbackQueryHandler

from app.bot.handlers.onboarding import onboarding_handler, integrations_callback
from app.bot.handlers.integrations import (
    connect_command,
    disconnect_command,
)
from app.bot.handlers.chat import chat_handler
from app.bot.handlers.stock import price_command
from app.providers.google import close_http_clients


PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(PROJECT_ROOT)
    )



load_dotenv()


TOKEN = os.getenv(
    "TELEGRAM_BOT_TOKEN"
)

LOCK_FILE = (
    Path(__file__)
    .resolve()
    .parent
    / ".bot.lock"
)

def cleanup_lock():

    if LOCK_FILE.exists():

        LOCK_FILE.unlink()



atexit.register(
    cleanup_lock
)



async def _post_shutdown(application):

    await close_http_clients()


def main():

    if LOCK_FILE.exists():

        print(
            "Another bot instance is already running."
        )

        sys.exit(1)



    LOCK_FILE.write_text(
        str(os.getpid())
    )


    application = (
        Application
        .builder()
        .token(TOKEN)
        .post_shutdown(_post_shutdown)
        .build()
    )


    application.add_handler(
        onboarding_handler
    )
    application.add_handler(
        CallbackQueryHandler(
            integrations_callback,
            pattern=r"^integration_",
        )
    )
    application.add_handler(
        MessageHandler(
            (filters.TEXT | filters.VOICE | filters.PHOTO) & ~filters.COMMAND,
            chat_handler,
        )
    )
    application.add_handler(
        CommandHandler(
            "price",
            price_command,
        )
    )
    application.add_handler(
        CommandHandler(
            "connect",
            connect_command,
        )
    )
    application.add_handler(
        CommandHandler(
            "disconnect",
            disconnect_command,
        )
    )


    try:

        application.run_polling()


    except Exception as exc:

        if (
            "Conflict" in str(exc)
            or
            "terminated by other getUpdates request" in str(exc)
        ):

            print(
                "Another bot instance is already running."
            )

        else:

            raise


    finally:

        cleanup_lock()

if __name__ == "__main__":
    main()