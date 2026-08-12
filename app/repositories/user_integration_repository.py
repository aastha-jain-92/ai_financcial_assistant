from datetime import datetime, timezone
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
        access_token: Optional[str] = None,
        refresh_token: Optional[str] = None,
        token_expires_at: Optional[datetime] = None,
        scopes: Optional[str] = None,
        google_email: Optional[str] = None,
        last_error: Optional[str] = None,
    ) -> UserIntegration:
        """
        Upsert an integration record for the user.

        Only the fields that are supplied are overwritten, so a token
        refresh never wipes the refresh token Google omits from its
        response.
        """

        existing = self.get_by_user_and_service(
            user_id, service_name
        )

        if existing is None:
            existing = UserIntegration(
                user_id=user_id,
                service_name=service_name,
            )
            self.db.add(existing)

        existing.is_connected = is_connected
        existing.last_error = last_error

        if access_token is not None:
            existing.access_token = access_token

        if refresh_token is not None:
            existing.refresh_token = refresh_token

        if token_expires_at is not None:
            existing.token_expires_at = token_expires_at

        if scopes is not None:
            existing.scopes = scopes

        if google_email is not None:
            existing.google_email = google_email

        if is_connected and existing.connected_at is None:
            existing.connected_at = datetime.now(timezone.utc)

        self.db.flush()

        return existing

    # ---------------------------------------------------------
    # Token maintenance
    # ---------------------------------------------------------

    def get_for_update(
        self,
        user_id: int,
        service_name: str,
    ) -> Optional[UserIntegration]:
        """
        Row-locked read used while refreshing an access token so that
        two concurrent requests cannot refresh the same grant twice.

        Backends without row locking (SQLite) simply ignore the lock.
        """

        query = self.db.query(UserIntegration).filter(
            UserIntegration.user_id == user_id,
            UserIntegration.service_name == service_name,
        )

        try:
            return query.with_for_update().first()
        except Exception:
            self.db.rollback()
            return query.first()

    def update_tokens(
        self,
        integration: UserIntegration,
        access_token: str,
        token_expires_at: datetime,
        refresh_token: Optional[str] = None,
        scopes: Optional[str] = None,
    ) -> UserIntegration:

        integration.access_token = access_token
        integration.token_expires_at = token_expires_at
        integration.is_connected = True
        integration.last_error = None

        if refresh_token:
            integration.refresh_token = refresh_token

        if scopes:
            integration.scopes = scopes

        self.db.flush()

        return integration

    def mark_disconnected(
        self,
        user_id: int,
        service_name: str,
        reason: Optional[str] = None,
        clear_tokens: bool = True,
    ) -> Optional[UserIntegration]:
        """
        Flag a service as disconnected (revoked, expired or user request).
        """

        integration = self.get_by_user_and_service(
            user_id, service_name
        )

        if integration is None:
            return None

        integration.is_connected = False
        integration.last_error = (reason or None)

        if clear_tokens:
            integration.access_token = None
            integration.refresh_token = None
            integration.token_expires_at = None

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
                UserIntegration.is_connected.is_(True),
            )
            .all()
        )

        return [row[0] for row in integrations]
