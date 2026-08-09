from datetime import datetime, timedelta, timezone
from typing import List

from sqlalchemy.orm import Session

from app.models.conversation import ConversationHistory


class ConversationRepository:
    """
    Repository responsible for managing conversation history.

    This class keeps database operations separate from the
    AI service and Telegram handlers.
    """

    def __init__(self, db: Session):
        self.db = db

    # ---------------------------------------------------------
    # Save Message
    # ---------------------------------------------------------

    def save_message(
        self,
        user_id: int,
        role: str,
        message: str,
    ) -> ConversationHistory:
        """
        Save a single conversation message.

        role should normally be:
            - user
            - assistant
            - system
        """

        conversation = ConversationHistory(
            user_id=user_id,
            role=role,
            message=message,
        )

        self.db.add(conversation)
        self.db.commit()
        self.db.refresh(conversation)

        return conversation

    # ---------------------------------------------------------
    # Get Recent Messages
    # ---------------------------------------------------------

    def get_recent_messages(
        self,
        user_id: int,
        limit: int = 10,
    ) -> List[ConversationHistory]:
        """
        Get the user's most recent conversation messages.

        Messages are returned in chronological order so they
        can be directly passed to the AI prompt builder.
        """

        if limit <= 0:
            return []

        messages = (
            self.db.query(ConversationHistory)
            .filter(
                ConversationHistory.user_id == user_id
            )
            .order_by(
                ConversationHistory.created_at.desc(),
                ConversationHistory.id.desc(),
            )
            .limit(limit)
            .all()
        )

        # Database query returns newest first.
        # Reverse so AI receives conversation chronologically.
        messages.reverse()

        return messages

    # ---------------------------------------------------------
    # Delete Old Messages
    # ---------------------------------------------------------

    def delete_old_messages(
        self,
        user_id: int,
        days: int = 30,
    ) -> int:
        """
        Delete conversation messages older than the
        specified number of days.

        Returns the number of deleted messages.
        """

        if days <= 0:
            return 0

        cutoff_date = datetime.now(timezone.utc) - timedelta(
            days=days
        )

        deleted_count = (
            self.db.query(ConversationHistory)
            .filter(
                ConversationHistory.user_id == user_id,
                ConversationHistory.created_at < cutoff_date,
            )
            .delete(
                synchronize_session=False
            )
        )

        return deleted_count

