from abc import ABC, abstractmethod
from typing import List

from sqlalchemy.orm import Session

from app.models.notification_preference import NotificationPreference
from app.repositories.base_repository import BaseRepository


class NotificationPreferenceRepository(ABC):
    """
    Interface for Notification Preference Repository.
    """

    @abstractmethod
    def get_by_user_id(
        self,
        user_id: int,
    ) -> List[NotificationPreference]:
        pass

    @abstractmethod
    def save_preferences(
        self,
        user_id: int,
        preferences: list[str],
    ) -> List[NotificationPreference]:
        pass

    @abstractmethod
    def delete_preferences(
        self,
        user_id: int,
    ) -> None:
        pass


class SQLAlchemyNotificationPreferenceRepository(
    BaseRepository[NotificationPreference],
    NotificationPreferenceRepository,
):

    def __init__(self, db: Session):
        super().__init__(db, NotificationPreference)

    def get_by_user_id(
        self,
        user_id: int,
    ) -> List[NotificationPreference]:

        return (
            self.db.query(NotificationPreference)
            .filter(NotificationPreference.user_id == user_id)
            .order_by(NotificationPreference.notification_type)
            .all()
        )

    def delete_preferences(
        self,
        user_id: int,
    ) -> None:

        (
            self.db.query(NotificationPreference)
            .filter(NotificationPreference.user_id == user_id)
            .delete()
        )

        self.db.commit()

    def save_preferences(
        self,
        user_id: int,
        preferences: list[str],
    ) -> List[NotificationPreference]:

        # Remove existing preferences
        self.delete_preferences(user_id)

        saved_preferences = []

        for preference in preferences:

            preference = preference.strip()

            if not preference:
                continue

            notification = self.create(
                user_id=user_id,
                notification_type=preference,
            )

            saved_preferences.append(notification)

        return saved_preferences