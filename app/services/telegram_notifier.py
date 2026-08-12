"""Best-effort Telegram notifications sent from the web process.

The OAuth callback runs inside FastAPI, not the bot, so it pushes the
"service connected" confirmation straight to the Bot API.
"""

import logging
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org"


async def send_message(
    chat_id: Optional[str],
    text: str,
) -> bool:
    """Send a Telegram message; never raises."""

    if not chat_id or not settings.TELEGRAM_BOT_TOKEN:
        return False

    url = (
        f"{TELEGRAM_API}/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    )

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                url,
                json={
                    "chat_id": chat_id,
                    "text": text,
                    "disable_web_page_preview": True,
                },
            )

        if response.status_code >= 300:
            logger.warning(
                "Telegram notification failed (%s): %s",
                response.status_code,
                response.text[:200],
            )
            return False

        return True

    except httpx.HTTPError as exc:
        logger.warning("Telegram notification failed: %s", exc)
        return False
