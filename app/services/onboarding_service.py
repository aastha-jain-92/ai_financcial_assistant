from sqlalchemy.orm import Session

from app.models.user import User

from app.repositories.user_repository import (
    SQLAlchemyUserRepository,
)

from app.repositories.user_preference_repository import (
    SQLAlchemyUserPreferenceRepository,
)

from app.repositories.watchlist_repository import (
    SQLAlchemyWatchlistRepository,
)

from app.repositories.notification_preference_repository import (
    SQLAlchemyNotificationPreferenceRepository,
)


class OnboardingService:

    def __init__(self, db: Session):

        self.db = db

        self.user_repository = SQLAlchemyUserRepository(db)

        self.preference_repository = (
            SQLAlchemyUserPreferenceRepository(db)
        )

        self.watchlist_repository = (
            SQLAlchemyWatchlistRepository(db)
        )

        self.notification_repository = (
            SQLAlchemyNotificationPreferenceRepository(db)
        )

    def complete_onboarding(
        self,
        telegram_id: int,
        full_name: str,
        role: str,
        companies: str,
        market: str,
        preferences: str,
        briefing_time: str,
    ) -> User:

        try:

            # --------------------------------------------------
            # Step 1 : Find Existing User
            # --------------------------------------------------

            user = self.user_repository.get_by_telegram_id(
                telegram_id
            )

            # --------------------------------------------------
            # Step 2 : Create User if not exists
            # --------------------------------------------------

            if user is None:

                user = self.user_repository.create(
                    telegram_id=telegram_id,
                    full_name=full_name,
                )

            # --------------------------------------------------
            # Step 3 : Save User Preference
            # --------------------------------------------------

            self.preference_repository.create_or_update(
                user_id=user.id,
                role=role,
                market=market,
                briefing_time=briefing_time,
            )

            # --------------------------------------------------
            # Step 4 : Save Watchlist
            # --------------------------------------------------

            company_list = [
                company.strip()
                for company in companies.split(",")
                if company.strip() and company.strip().lower() != "skip"
            ]

            self.watchlist_repository.save_watchlist(
                user.id,
                company_list,
            )

            # --------------------------------------------------
            # Step 5 : Save Notification Preference
            # --------------------------------------------------

            preference_list = [
                preference.strip()
                for preference in preferences.split(",")
                if preference.strip()
                and preference.strip().lower() != "skip"
            ]

            self.notification_repository.save_preferences(
                user.id,
                preference_list,
            )

            # --------------------------------------------------
            # Step 6 : Complete Onboarding
            # --------------------------------------------------

            self.user_repository.mark_onboarding_completed(
                user
            )

            return user

        except Exception:

            self.db.rollback()

            raise