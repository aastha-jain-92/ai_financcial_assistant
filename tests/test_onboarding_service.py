import os
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_onboarding.db")

from app.database.database import Base, SessionLocal, engine
from app.repositories.user_repository import SQLAlchemyUserRepository
from app.services.onboarding_service import OnboardingService


class OnboardingServiceTest(unittest.TestCase):
    def setUp(self):
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        self.repo = SQLAlchemyUserRepository(SessionLocal)
        self.service = OnboardingService(self.repo)

    def tearDown(self):
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
        if Path("test_onboarding.db").exists():
            Path("test_onboarding.db").unlink(missing_ok=True)

    def test_complete_onboarding_creates_user(self):
        user = self.service.complete_onboarding(
            telegram_id=12345,
            full_name="Alice Example",
            role="Investor",
            companies="Apple, Tesla",
            market="US Market",
            preferences="Market News,Earnings",
            briefing_time="08:00 AM",
        )

        self.assertEqual(user.role, "Investor")
        self.assertTrue(user.onboarding_completed)

        saved_user = self.repo.get_by_telegram_id(12345)
        self.assertIsNotNone(saved_user)
        self.assertEqual(saved_user.full_name, "Alice Example")


if __name__ == "__main__":
    unittest.main()
