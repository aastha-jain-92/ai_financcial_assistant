from abc import ABC, abstractmethod
from typing import Optional

from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories.base_repository import BaseRepository


class UserRepository(ABC):
    """
    Interface for User Repository.
    """

    @abstractmethod
    def get_by_telegram_id(
        self,
        telegram_id: int,
    ) -> Optional[User]:
        pass

    @abstractmethod
    def mark_onboarding_completed(
        self,
        user: User,
    ) -> User:
        pass


class SQLAlchemyUserRepository(
    BaseRepository[User],
    UserRepository,
):
    """
    SQLAlchemy implementation of User Repository.
    """

    def __init__(self, db: Session):
        super().__init__(db, User)

    def get_by_telegram_id(
        self,
        telegram_id: int,
    ) -> Optional[User]:

        return (
            self.db.query(User)
            .filter(User.telegram_id == telegram_id)
            .first()
        )

    def mark_onboarding_completed(
        self,
        user: User,
    ) -> User:

        return self.update(
            user,
            onboarding_completed=True,
        )