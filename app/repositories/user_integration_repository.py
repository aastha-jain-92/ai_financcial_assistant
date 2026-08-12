from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.user_integration import UserIntegration


class SQLAlchemyUserIntegrationRepository:
    """
    Repository for managing user Google-service integrations.
    """

    def __init__(self, db: Session):
        self.db = db

    # ---------------------------------------------------------
    # Get All Integrations for a User
    # ---------------------------------------------------------

    def get_by_user_id(
        self,
        user_id: int,
    ) -> List[UserIntegration]:
        """
        Return all integration rows for the given user.
        """

        return (
            self.db.query(UserIntegration)
            .filter(UserIntegration.user_id == user_id)
            .all()
        )

    # ---------------------------------------------------------
    # Get a Specific Integration
    # ---------------------------------------------------------

    def get_by_user_and_service(
        self,
        user_id: int,
        service_name: str,
    ) -> Optional[UserIntegration]:
        """
        Return the integration row for a specific service,
        or None if it doesn't exist yet.
        """

        return (
            self.db.query(UserIntegration)
            .filter(
                UserIntegration.user_id == user_id,
                UserIntegration.service_name == service_name,
            )
            .first()
        )

    # ---------------------------------------------------------
    # Create or Update
    # ---------------------------------------------------------

    def create_or_update(
        self,
        user_id: int,
        service_name: str,
        is_connected: bool = False,
        access_token: str = None,
        refresh_token: str = None,
    ) -> UserIntegration:
        """
        Upsert an integration record for the user.
        """

        existing = self.get_by_user_and_service(
            user_id, service_name
        )

        if existing:
            existing.is_connected = is_connected
            if access_token:
                existing.access_token = access_token
            if refresh_token:
                existing.refresh_token = refresh_token
            self.db.flush()
            return existing

        integration = UserIntegration(
            user_id=user_id,
            service_name=service_name,
            is_connected=is_connected,
            access_token=access_token,
            refresh_token=refresh_token,
        )

        self.db.add(integration)
        self.db.flush()

        return integration

    # ---------------------------------------------------------
    # Get Connected Services
    # ---------------------------------------------------------

    def get_connected_services(
        self,
        user_id: int,
    ) -> List[str]:
        """
        Return a list of service names that the user
        has successfully connected.
        """

        integrations = (
            self.db.query(UserIntegration.service_name)
            .filter(
                UserIntegration.user_id == user_id,
                UserIntegration.is_connected == True,
            )
            .all()
        )

        return [row[0] for row in integrations]
