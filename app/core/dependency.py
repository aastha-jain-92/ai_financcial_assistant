from app.database.database import SessionLocal
from app.repositories.user_repository import SQLAlchemyUserRepository
from app.services.onboarding_service import OnboardingService


def get_onboarding_service():

    db = SessionLocal()

    repository = SQLAlchemyUserRepository(db)

    service = OnboardingService(repository)

    return service, db