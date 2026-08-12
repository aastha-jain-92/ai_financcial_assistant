"""Encryption helper for OAuth tokens stored in the database."""

import logging
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings

logger = logging.getLogger(__name__)

ENCRYPTED_PREFIX = "enc::"


class TokenCipher:
    """Encrypts tokens at rest when an encryption key is configured.

    Values written before a key existed stay readable: anything without
    the ``enc::`` prefix is returned as-is.
    """

    def __init__(self, key: Optional[str] = None):
        raw_key = (
            key
            if key is not None
            else settings.GOOGLE_TOKEN_ENCRYPTION_KEY
        )

        self._fernet: Optional[Fernet] = None

        if raw_key:
            try:
                self._fernet = Fernet(raw_key.encode())
            except (ValueError, TypeError):
                logger.error(
                    "GOOGLE_TOKEN_ENCRYPTION_KEY is not a valid Fernet key; "
                    "tokens will be stored in plain text."
                )
        else:
            logger.warning(
                "GOOGLE_TOKEN_ENCRYPTION_KEY is not set; "
                "Google OAuth tokens will be stored in plain text."
            )

    @property
    def enabled(self) -> bool:
        return self._fernet is not None

    def encrypt(self, value: Optional[str]) -> Optional[str]:

        if not value or self._fernet is None:
            return value

        return ENCRYPTED_PREFIX + self._fernet.encrypt(
            value.encode()
        ).decode()

    def decrypt(self, value: Optional[str]) -> Optional[str]:

        if not value or not value.startswith(ENCRYPTED_PREFIX):
            return value

        if self._fernet is None:
            logger.error(
                "Stored token is encrypted but no encryption key is set."
            )
            return None

        try:
            return self._fernet.decrypt(
                value[len(ENCRYPTED_PREFIX):].encode()
            ).decode()
        except InvalidToken:
            logger.error(
                "Stored token could not be decrypted; "
                "GOOGLE_TOKEN_ENCRYPTION_KEY may have changed."
            )
            return None
