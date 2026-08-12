"""Google OAuth callback.

Google redirects the user here after consent. We validate the one-time
`state`, exchange the code for tokens, store them against the Telegram
user, and confirm back in Telegram.
"""

import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database.database import SessionLocal
from app.providers.google import (
    SERVICE_LABELS,
    SERVICE_SCOPES,
    GoogleError,
    GoogleOAuthClient,
)
from app.repositories.oauth_state_repository import (
    SQLAlchemyOAuthStateRepository,
)
from app.services.google.token_service import GoogleTokenService
from app.services.telegram_notifier import send_message

logger = logging.getLogger(__name__)

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/auth/google/callback")
async def google_auth_callback(
    request: Request,
    db: Session = Depends(get_db),
):

    error = request.query_params.get("error")

    if error:
        return _page(
            "Google authorization was cancelled",
            f"Google reported: {error}. You can retry with /connect "
            "in Telegram.",
            status_code=400,
        )

    code = request.query_params.get("code")
    state = request.query_params.get("state")

    if not code or not state:
        return _page(
            "Google authorization failed",
            "The authorization code or state parameter is missing.",
            status_code=400,
        )

    state_repository = SQLAlchemyOAuthStateRepository(db)
    oauth_state = state_repository.consume(state)

    if oauth_state is None:
        db.rollback()
        return _page(
            "This link has expired",
            "Authorization links can only be used once and expire "
            "after a few minutes. Run /connect in Telegram to get a "
            "fresh link.",
            status_code=400,
        )

    db.commit()

    service_name = oauth_state.service_name
    label = SERVICE_LABELS.get(service_name, service_name)

    oauth_client = GoogleOAuthClient()

    try:
        tokens = await oauth_client.exchange_code(code)
        email = await oauth_client.get_user_email(tokens.access_token)

    except GoogleError:
        logger.exception(
            "Google token exchange failed (user=%s service=%s)",
            oauth_state.user_id,
            service_name,
        )
        return _page(
            "Could not complete the connection",
            "Google refused the authorization code. Please run "
            "/connect in Telegram and try again.",
            status_code=502,
        )

    missing_scopes = [
        scope
        for scope in SERVICE_SCOPES.get(service_name, ())
        if scope not in tokens.scopes and scope != "openid"
    ]

    if missing_scopes:
        logger.warning(
            "User %s granted partial scopes for %s: missing %s",
            oauth_state.user_id,
            service_name,
            missing_scopes,
        )

    token_service = GoogleTokenService(db, oauth_client=oauth_client)

    try:
        token_service.store_tokens(
            user_id=oauth_state.user_id,
            service_name=service_name,
            tokens=tokens,
            google_email=email,
        )
        db.commit()

    except Exception:
        db.rollback()
        logger.exception(
            "Could not store Google tokens (user=%s service=%s)",
            oauth_state.user_id,
            service_name,
        )
        return _page(
            "Could not save the connection",
            "Something went wrong on our side. Please try /connect "
            "again in Telegram.",
            status_code=500,
        )

    await send_message(
        oauth_state.telegram_chat_id,
        f"✅ {label} is now connected"
        + (f" ({email})." if email else ".")
        + "\n\nAsk me anything that needs it — for example "
        "\"summarise my latest bank emails\" or \"what's in my "
        "portfolio sheet\".",
    )

    if missing_scopes:
        return _page(
            f"{label} connected with limited access",
            "Some permissions were not granted, so a few answers may "
            "be incomplete. You can reconnect from Telegram to grant "
            "full read access.",
        )

    return _page(
        f"{label} connected",
        "You can close this tab and return to Telegram.",
    )


def _page(
    title: str,
    body: str,
    status_code: int = 200,
) -> HTMLResponse:

    icon = "✅" if status_code < 300 else "⚠️"

    return HTMLResponse(
        f"""
        <html>
            <head>
                <meta name="viewport"
                      content="width=device-width, initial-scale=1" />
                <title>{title}</title>
            </head>
            <body style="font-family: system-ui, sans-serif;
                         max-width: 32rem; margin: 4rem auto;
                         text-align: center;">
                <h2>{icon} {title}</h2>
                <p>{body}</p>
            </body>
        </html>
        """,
        status_code=status_code,
    )
