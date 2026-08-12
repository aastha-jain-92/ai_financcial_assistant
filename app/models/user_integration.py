from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Boolean,
    DateTime,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.database.database import Base


class UserIntegration(Base):
    """
    Tracks which Google services a user has connected.

    Each row represents one service for one user
    (e.g. user 1 ↔ gmail, user 1 ↔ google_calendar).
    """

    __tablename__ = "user_integrations"

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "service_name",
            name="uq_user_integration_service",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    service_name = Column(
        String(50),
        nullable=False,
    )
    # Allowed values:
    # "gmail"+
    # "google_calendar"
    # "google_drive"
    # "google_sheets"

    is_connected = Column(
        Boolean,
        default=False,
        nullable=False,
    )

    connected_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Tokens are encrypted at rest when GOOGLE_TOKEN_ENCRYPTION_KEY is set.
    access_token = Column(Text, nullable=True)
    refresh_token = Column(Text, nullable=True)

    token_expires_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    scopes = Column(Text, nullable=True)

    google_email = Column(String(255), nullable=True)

    last_error = Column(String(255), nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user = relationship(
        "User",
        back_populates="integrations",
    )
