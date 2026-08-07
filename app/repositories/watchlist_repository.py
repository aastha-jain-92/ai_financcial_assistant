from abc import ABC, abstractmethod
from typing import List

from sqlalchemy.orm import Session

from app.models.watchlist import Watchlist
from app.repositories.base_repository import BaseRepository


class WatchlistRepository(ABC):
    """
    Interface for Watchlist Repository.
    """

    @abstractmethod
    def get_by_user_id(
        self,
        user_id: int,
    ) -> List[Watchlist]:
        pass

    @abstractmethod
    def save_watchlist(
        self,
        user_id: int,
        companies: list[str],
    ) -> List[Watchlist]:
        pass

    @abstractmethod
    def delete_watchlist(
        self,
        user_id: int,
    ) -> None:
        pass


class SQLAlchemyWatchlistRepository(
    BaseRepository[Watchlist],
    WatchlistRepository,
):

    def __init__(self, db: Session):
        super().__init__(db, Watchlist)

    def get_by_user_id(
        self,
        user_id: int,
    ) -> List[Watchlist]:

        return (
            self.db.query(Watchlist)
            .filter(Watchlist.user_id == user_id)
            .order_by(Watchlist.company_name)
            .all()
        )

    def delete_watchlist(
        self,
        user_id: int,
    ) -> None:

        (
            self.db.query(Watchlist)
            .filter(Watchlist.user_id == user_id)
            .delete()
        )

        self.db.commit()

    def save_watchlist(
        self,
        user_id: int,
        companies: list[str],
    ) -> List[Watchlist]:

        # Remove existing companies
        self.delete_watchlist(user_id)

        watchlists = []

        for company in companies:

            company = company.strip()

            if not company:
                continue

            watchlist = self.create(
                user_id=user_id,
                company_name=company,
            )

            watchlists.append(watchlist)

        return watchlists