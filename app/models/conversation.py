from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    func,
)
from sqlalchemy.orm import relationship

from app.database.database import Base


class ConversationHistory(Base):
    """
    Stores the conversation history between a Telegram user
    and the AI assistant.
    """

    __tablename__ = "conversation_history"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    user_id = Column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    role = Column(
        Text,
        nullable=False,
    )
    # Allowed values:
    # "system"
    # "user"
    # "assistant"

    message = Column(
        Text,
        nullable=False,
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    user = relationship(
        "User",
        back_populates="conversation_history",
    )