import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.models.oauth_state import OAuthState
from app.utils.datetime_utils import as_utc


class SQLAlchemyOAuthStateRepository:
    """Persistence for single-use Google OAuth `state` values."""

    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        user_id: int,
        service_name: str,
        telegram_chat_id: Optional[str] = None,
        ttl_seconds: Optional[int] = None,
    ) -> OAuthState:

        ttl = ttl_seconds or settings.GOOGLE_OAUTH_STATE_TTL_SECONDS

        oauth_state = OAuthState(
            state=secrets.token_urlsafe(32),
            user_id=user_id,
            service_name=service_name,
            telegram_chat_id=(
                str(telegram_chat_id) if telegram_chat_id else None
            ),
            expires_at=datetime.now(timezone.utc)
            + timedelta(seconds=ttl),
        )

        self.db.add(oauth_state)
        self.db.flush()

        return oauth_state

    def get_by_state(self, state: str) -> Optional[OAuthState]:

        return (
            self.db.query(OAuthState)
            .filter(OAuthState.state == state)
            .first()
        )

    def consume(self, state: str) -> Optional[OAuthState]:
        """Return the state row and mark it used, or None if unusable."""

        record = self.get_by_state(state)

        if record is None or record.consumed_at is not None:
            return None

        if as_utc(record.expires_at) < datetime.now(timezone.utc):
            return None

        record.consumed_at = datetime.now(timezone.utc)
        self.db.flush()

        return record

    def delete_expired(self) -> int:
        """Housekeeping: drop states that can no longer be used."""

        deleted = (
            self.db.query(OAuthState)
            .filter(OAuthState.expires_at < datetime.now(timezone.utc))
            .delete(synchronize_session=False)
        )

        return int(deleted or 0)
