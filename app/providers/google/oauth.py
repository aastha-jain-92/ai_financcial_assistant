"""Google OAuth 2.0 authorization-code flow."""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from urllib.parse import urlencode

from app.config import settings

from .constants import (
    AUTH_ENDPOINT,
    REVOKE_ENDPOINT,
    SERVICE_SCOPES,
    TOKEN_ENDPOINT,
    USERINFO_ENDPOINT,
)
from .exceptions import (
    GoogleAPIError,
    GoogleError,
    GoogleNotConfigured,
)
from .http import request_json

logger = logging.getLogger(__name__)


@dataclass
class GoogleTokens:
    access_token: str
    expires_at: datetime
    refresh_token: Optional[str] = None
    scopes: List[str] = field(default_factory=list)

    @property
    def scope_string(self) -> str:
        return " ".join(self.scopes)


class GoogleOAuthClient:
    """Thin client around Google's OAuth endpoints."""

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        redirect_uri: Optional[str] = None,
    ):
        self.client_id = client_id or settings.GOOGLE_CLIENT_ID
        self.client_secret = (
            client_secret or settings.GOOGLE_CLIENT_SECRET
        )
        self.redirect_uri = (
            redirect_uri or settings.GOOGLE_REDIRECT_URI
        )

    def _require_config(self) -> None:
        if not (
            self.client_id
            and self.client_secret
            and self.redirect_uri
        ):
            raise GoogleNotConfigured(
                "Set GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET and "
                "GOOGLE_REDIRECT_URI before using Google integrations."
            )

    # -----------------------------------------------------
    # Step 1: consent URL
    # -----------------------------------------------------

    def build_authorization_url(
        self,
        service_name: str,
        state: str,
    ) -> str:

        self._require_config()

        scopes = SERVICE_SCOPES.get(service_name)

        if not scopes:
            raise GoogleError(
                f"Unsupported Google service: {service_name}"
            )

        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": " ".join(scopes),
            "access_type": "offline",
            "include_granted_scopes": "true",
            "prompt": "consent",
            "state": state,
        }

        return f"{AUTH_ENDPOINT}?{urlencode(params)}"

    # -----------------------------------------------------
    # Step 2: code -> tokens
    # -----------------------------------------------------

    async def exchange_code(self, code: str) -> GoogleTokens:

        self._require_config()

        payload = await request_json(
            "POST",
            TOKEN_ENDPOINT,
            data={
                "code": code,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "redirect_uri": self.redirect_uri,
                "grant_type": "authorization_code",
            },
        )

        return self._to_tokens(payload)

    # -----------------------------------------------------
    # Step 3: refresh
    # -----------------------------------------------------

    async def refresh_access_token(
        self,
        refresh_token: str,
    ) -> GoogleTokens:

        self._require_config()

        payload = await request_json(
            "POST",
            TOKEN_ENDPOINT,
            data={
                "refresh_token": refresh_token,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "grant_type": "refresh_token",
            },
        )

        tokens = self._to_tokens(payload)

        # Google does not return the refresh token on refresh responses.
        tokens.refresh_token = tokens.refresh_token or refresh_token

        return tokens

    # -----------------------------------------------------
    # Revoke / userinfo
    # -----------------------------------------------------

    async def revoke(self, token: str) -> None:

        try:
            await request_json(
                "POST",
                REVOKE_ENDPOINT,
                data={"token": token},
                expect_json=False,
            )
        except GoogleAPIError as exc:
            # A token that is already invalid also counts as revoked.
            logger.info("Google token revocation returned %s", exc)

    async def get_user_email(self, access_token: str) -> Optional[str]:

        try:
            payload = await request_json(
                "GET",
                USERINFO_ENDPOINT,
                access_token=access_token,
            )
        except GoogleError as exc:
            logger.info("Could not read Google userinfo: %s", exc)
            return None

        if isinstance(payload, dict):
            return payload.get("email")

        return None

    # -----------------------------------------------------
    # Helpers
    # -----------------------------------------------------

    @staticmethod
    def _to_tokens(payload: object) -> GoogleTokens:

        if not isinstance(payload, dict) or not payload.get("access_token"):
            raise GoogleError(
                "Google token endpoint returned no access token."
            )

        expires_in = payload.get("expires_in") or 3600

        try:
            expires_in = int(expires_in)
        except (TypeError, ValueError):
            expires_in = 3600

        return GoogleTokens(
            access_token=str(payload["access_token"]),
            refresh_token=payload.get("refresh_token"),
            expires_at=datetime.now(timezone.utc)
            + timedelta(seconds=expires_in),
            scopes=str(payload.get("scope", "")).split(),
        )
