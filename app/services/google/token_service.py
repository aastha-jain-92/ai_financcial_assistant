"""Token lifecycle for the Google integration.

Stores, refreshes and revokes per-user OAuth grants, and hands out a
valid access token to the data layer.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.core.crypto import TokenCipher
from app.models.user_integration import UserIntegration
from app.providers.google import (
    GoogleError,
    GoogleNotConnected,
    GoogleOAuthClient,
    GoogleReauthRequired,
    GoogleTokens,
)
from app.repositories.user_integration_repository import (
    SQLAlchemyUserIntegrationRepository,
)
from app.utils.datetime_utils import as_utc

logger = logging.getLogger(__name__)


class GoogleTokenService:
    """Owns everything token related for one database session."""

    def __init__(
        self,
        db: Session,
        oauth_client: Optional[GoogleOAuthClient] = None,
        cipher: Optional[TokenCipher] = None,
    ):
        self.db = db
        self.oauth_client = oauth_client or GoogleOAuthClient()
        self.cipher = cipher or TokenCipher()
        self.repository = SQLAlchemyUserIntegrationRepository(db)

    # -----------------------------------------------------
    # Reads
    # -----------------------------------------------------

    def connected_services(self, user_id: int) -> List[str]:
        return self.repository.get_connected_services(user_id)

    def get_integration(
        self,
        user_id: int,
        service_name: str,
    ) -> Optional[UserIntegration]:
        return self.repository.get_by_user_and_service(
            user_id, service_name
        )

    # -----------------------------------------------------
    # Storing a fresh grant (OAuth callback)
    # -----------------------------------------------------

    def store_tokens(
        self,
        user_id: int,
        service_name: str,
        tokens: GoogleTokens,
        google_email: Optional[str] = None,
    ) -> UserIntegration:

        existing = self.get_integration(user_id, service_name)

        refresh_token = tokens.refresh_token

        if not refresh_token and existing is not None:
            # Google only returns a refresh token on first consent.
            refresh_token = existing.refresh_token
        elif refresh_token:
            refresh_token = self.cipher.encrypt(refresh_token)

        return self.repository.create_or_update(
            user_id=user_id,
            service_name=service_name,
            is_connected=True,
            access_token=self.cipher.encrypt(tokens.access_token),
            refresh_token=refresh_token,
            token_expires_at=tokens.expires_at,
            scopes=tokens.scope_string,
            google_email=google_email,
            last_error=None,
        )

    # -----------------------------------------------------
    # Handing out access tokens
    # -----------------------------------------------------

    async def get_access_token(
        self,
        user_id: int,
        service_name: str,
        force_refresh: bool = False,
    ) -> str:
        """Return a usable access token, refreshing it when needed."""

        integration = self.repository.get_for_update(
            user_id, service_name
        )

        if integration is None or not integration.is_connected:
            raise GoogleNotConnected(service_name)

        access_token = self.cipher.decrypt(integration.access_token)

        if (
            access_token
            and not force_refresh
            and not self._is_expiring(integration.token_expires_at)
        ):
            return access_token

        refresh_token = self.cipher.decrypt(integration.refresh_token)

        if not refresh_token:
            self._disconnect_locally(
                user_id,
                service_name,
                "No refresh token stored",
            )
            raise GoogleReauthRequired(
                service_name,
                "no refresh token stored",
            )

        try:
            tokens = await self.oauth_client.refresh_access_token(
                refresh_token
            )
        except GoogleError as exc:
            self._disconnect_locally(
                user_id,
                service_name,
                f"Token refresh failed: {exc}",
            )
            raise GoogleReauthRequired(
                service_name,
                "the Google authorization was revoked or expired",
            ) from exc

        self.repository.update_tokens(
            integration=integration,
            access_token=self.cipher.encrypt(tokens.access_token),
            token_expires_at=tokens.expires_at,
            refresh_token=(
                self.cipher.encrypt(tokens.refresh_token)
                if tokens.refresh_token
                and tokens.refresh_token != refresh_token
                else None
            ),
            scopes=tokens.scope_string or None,
        )
        self.db.commit()

        logger.info(
            "Refreshed Google access token (user=%s service=%s)",
            user_id,
            service_name,
        )

        return tokens.access_token

    # -----------------------------------------------------
    # Disconnecting
    # -----------------------------------------------------

    async def disconnect(
        self,
        user_id: int,
        service_name: str,
    ) -> bool:
        """Revoke the grant at Google and clear the stored tokens."""

        integration = self.get_integration(user_id, service_name)

        if integration is None:
            return False

        token = (
            self.cipher.decrypt(integration.refresh_token)
            or self.cipher.decrypt(integration.access_token)
        )

        if token:
            try:
                await self.oauth_client.revoke(token)
            except GoogleError as exc:
                logger.warning(
                    "Google revocation failed (user=%s service=%s): %s",
                    user_id,
                    service_name,
                    exc,
                )

        self.repository.mark_disconnected(
            user_id=user_id,
            service_name=service_name,
            reason="Disconnected by user",
        )
        self.db.commit()

        return True

    # -----------------------------------------------------
    # Helpers
    # -----------------------------------------------------

    @staticmethod
    def _is_expiring(expires_at: Optional[datetime]) -> bool:

        if expires_at is None:
            return True

        leeway = timedelta(
            seconds=settings.GOOGLE_TOKEN_REFRESH_LEEWAY_SECONDS
        )

        return as_utc(expires_at) - leeway <= datetime.now(timezone.utc)

    def _disconnect_locally(
        self,
        user_id: int,
        service_name: str,
        reason: str,
    ) -> None:

        self.repository.mark_disconnected(
            user_id=user_id,
            service_name=service_name,
            reason=reason[:255],
        )
        self.db.commit()
