from abc import ABC, abstractmethod
from typing import Optional

from sqlalchemy.orm import Session

from app.models.user_preference import UserPreference
from app.repositories.base_repository import BaseRepository


class UserPreferenceRepository(ABC):
    """
    Interface for User Preference Repository.
    """

    @abstractmethod
    def get_by_user_id(
        self,
        user_id: int,
    ) -> Optional[UserPreference]:
        pass

    @abstractmethod
    def create_or_update(
        self,
        user_id: int,
        role: str,
        market: str,
        briefing_time: str,
    ) -> UserPreference:
        pass


class SQLAlchemyUserPreferenceRepository(
    BaseRepository[UserPreference],
    UserPreferenceRepository,
):
    """
    SQLAlchemy implementation of User Preference Repository.
    """

    def __init__(self, db: Session):
        super().__init__(db, UserPreference)

    def get_by_user_id(
        self,
        user_id: int,
    ) -> Optional[UserPreference]:

        return (
            self.db.query(UserPreference)
            .filter(UserPreference.user_id == user_id)
            .first()
        )

    def create_or_update(
        self,
        user_id: int,
        role: str,
        market: str,
        briefing_time: str,
    ) -> UserPreference:

        preference = self.get_by_user_id(user_id)

        if preference:

            return self.update(
                preference,
                role=role,
                market=market,
                briefing_time=briefing_time,
            )

        return self.create(
            user_id=user_id,
            role=role,
            market=market,
            briefing_time=briefing_time,
        )