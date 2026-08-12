from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
)
from sqlalchemy.sql import func

from app.database.database import Base


class OAuthState(Base):
    """
    Short-lived, single-use CSRF token for the Google OAuth flow.

    The Telegram bot creates one row per consent link and the OAuth
    callback consumes it to learn which user/service the code belongs to.
    """

    __tablename__ = "oauth_states"

    id = Column(Integer, primary_key=True, index=True)

    state = Column(
        String(128),
        nullable=False,
        unique=True,
        index=True,
    )

    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    service_name = Column(String(50), nullable=False)

    telegram_chat_id = Column(
        String(64),
        nullable=True,
    )

    expires_at = Column(
        DateTime(timezone=True),
        nullable=False,
    )

    consumed_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
