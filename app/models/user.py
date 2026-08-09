from sqlalchemy import (
    Column,
    Integer,
    BigInteger,
    String,
    Boolean,
    DateTime,
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.database.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)

    telegram_id = Column(
        BigInteger,
        unique=True,
        nullable=False,
        index=True,
    )

    full_name = Column(String(100), nullable=False)

    onboarding_completed = Column(
        Boolean,
        default=False,
        nullable=False,
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    preference = relationship(
        "UserPreference",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )

    watchlists = relationship(
        "Watchlist",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    notification_preferences = relationship(
        "NotificationPreference",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    conversation_history = relationship(
        "ConversationHistory",
        back_populates="user",
        cascade="all, delete-orphan",
        order_by="ConversationHistory.created_at",
    )