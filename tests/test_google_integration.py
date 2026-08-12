import asyncio
import json
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_google.db")

from cryptography.fernet import Fernet  # noqa: E402

from app.core.crypto import TokenCipher  # noqa: E402
from app.database.database import (  # noqa: E402
    Base,
    SessionLocal,
    engine,
)
from app.models.conversation import (  # noqa: E402,F401
    ConversationHistory,
)
from app.models.notification_preference import (  # noqa: E402,F401
    NotificationPreference,
)
from app.models.oauth_state import OAuthState  # noqa: E402
from app.models.user import User  # noqa: E402
from app.models.user_integration import UserIntegration  # noqa: E402
from app.models.user_preference import (  # noqa: E402,F401
    UserPreference,
)
from app.models.watchlist import Watchlist  # noqa: E402,F401
from app.providers.google import (  # noqa: E402
    GMAIL,
    GOOGLE_CALENDAR,
    GOOGLE_DRIVE,
    GOOGLE_SHEETS,
    GoogleNotConnected,
    GoogleTokens,
    GoogleUnauthorized,
    normalize_service,
)
from app.providers.google import gmail as gmail_provider  # noqa: E402
from app.services.google import (  # noqa: E402
    google_service as google_service_module,
)
from app.repositories.oauth_state_repository import (  # noqa: E402
    SQLAlchemyOAuthStateRepository,
)
from app.services.google.token_service import (  # noqa: E402
    GoogleTokenService,
)
from app.services.tools import ToolRegistry, ToolSpec  # noqa: E402
from app.services.tools.google_tools import (  # noqa: E402
    build_google_tools,
    google_tools_prompt,
)

DB_FILE = Path("test_google.db")


def run(coro):
    return asyncio.run(coro)


class DatabaseTestCase(unittest.TestCase):
    def setUp(self):
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        self.db = SessionLocal()
        self.user = User(telegram_id=4242, full_name="Test User")
        self.db.add(self.user)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
        DB_FILE.unlink(missing_ok=True)


# ---------------------------------------------------------
# Token encryption
# ---------------------------------------------------------


class TokenCipherTest(unittest.TestCase):
    def test_roundtrip_with_key(self):
        cipher = TokenCipher(key=Fernet.generate_key().decode())

        encrypted = cipher.encrypt("ya29.secret-token")

        self.assertNotIn("ya29.secret-token", encrypted)
        self.assertEqual(
            cipher.decrypt(encrypted), "ya29.secret-token"
        )

    def test_plaintext_passthrough_without_key(self):
        cipher = TokenCipher(key=None)

        self.assertEqual(cipher.encrypt("abc"), "abc")
        self.assertEqual(cipher.decrypt("abc"), "abc")

    def test_legacy_plaintext_is_still_readable(self):
        cipher = TokenCipher(key=Fernet.generate_key().decode())

        self.assertEqual(cipher.decrypt("legacy-plaintext"),
                         "legacy-plaintext")

    def test_none_is_preserved(self):
        cipher = TokenCipher(key=Fernet.generate_key().decode())

        self.assertIsNone(cipher.encrypt(None))
        self.assertIsNone(cipher.decrypt(None))


# ---------------------------------------------------------
# OAuth state
# ---------------------------------------------------------


class OAuthStateRepositoryTest(DatabaseTestCase):
    def test_state_is_single_use(self):
        repo = SQLAlchemyOAuthStateRepository(self.db)
        created = repo.create(
            user_id=self.user.id,
            service_name=GMAIL,
            telegram_chat_id=999,
        )
        self.db.commit()

        consumed = repo.consume(created.state)

        self.assertIsNotNone(consumed)
        self.assertEqual(consumed.service_name, GMAIL)
        self.assertEqual(consumed.telegram_chat_id, "999")
        self.assertIsNone(repo.consume(created.state))

    def test_expired_state_is_rejected(self):
        repo = SQLAlchemyOAuthStateRepository(self.db)
        expired = OAuthState(
            state="expired-state",
            user_id=self.user.id,
            service_name=GMAIL,
            expires_at=datetime.now(timezone.utc)
            - timedelta(minutes=1),
        )
        self.db.add(expired)
        self.db.commit()

        self.assertIsNone(repo.consume("expired-state"))

    def test_unknown_state_is_rejected(self):
        repo = SQLAlchemyOAuthStateRepository(self.db)

        self.assertIsNone(repo.consume("never-issued"))


# ---------------------------------------------------------
# Token service
# ---------------------------------------------------------


class FakeOAuthClient:
    def __init__(self, tokens=None, error=None):
        self.tokens = tokens
        self.error = error
        self.refresh_calls = []
        self.revoked = []

    async def refresh_access_token(self, refresh_token):
        self.refresh_calls.append(refresh_token)

        if self.error:
            raise self.error

        return self.tokens

    async def revoke(self, token):
        self.revoked.append(token)


class GoogleTokenServiceTest(DatabaseTestCase):
    def setUp(self):
        super().setUp()
        self.cipher = TokenCipher(key=Fernet.generate_key().decode())

    def _service(self, oauth_client):
        return GoogleTokenService(
            self.db,
            oauth_client=oauth_client,
            cipher=self.cipher,
        )

    def test_store_tokens_encrypts_and_marks_connected(self):
        service = self._service(FakeOAuthClient())

        service.store_tokens(
            user_id=self.user.id,
            service_name=GMAIL,
            tokens=GoogleTokens(
                access_token="access-1",
                refresh_token="refresh-1",
                expires_at=datetime.now(timezone.utc)
                + timedelta(hours=1),
                scopes=["scope-a"],
            ),
            google_email="user@example.com",
        )
        self.db.commit()

        row = (
            self.db.query(UserIntegration)
            .filter_by(user_id=self.user.id, service_name=GMAIL)
            .one()
        )

        self.assertTrue(row.is_connected)
        self.assertNotIn("access-1", row.access_token)
        self.assertEqual(row.google_email, "user@example.com")
        self.assertEqual(
            service.connected_services(self.user.id), [GMAIL]
        )

    def test_valid_token_is_returned_without_refresh(self):
        client = FakeOAuthClient()
        service = self._service(client)

        service.store_tokens(
            user_id=self.user.id,
            service_name=GMAIL,
            tokens=GoogleTokens(
                access_token="access-1",
                refresh_token="refresh-1",
                expires_at=datetime.now(timezone.utc)
                + timedelta(hours=1),
            ),
        )
        self.db.commit()

        token = run(
            service.get_access_token(self.user.id, GMAIL)
        )

        self.assertEqual(token, "access-1")
        self.assertEqual(client.refresh_calls, [])

    def test_expired_token_is_refreshed(self):
        client = FakeOAuthClient(
            tokens=GoogleTokens(
                access_token="access-2",
                refresh_token=None,
                expires_at=datetime.now(timezone.utc)
                + timedelta(hours=1),
            )
        )
        service = self._service(client)

        service.store_tokens(
            user_id=self.user.id,
            service_name=GMAIL,
            tokens=GoogleTokens(
                access_token="access-1",
                refresh_token="refresh-1",
                expires_at=datetime.now(timezone.utc)
                - timedelta(minutes=5),
            ),
        )
        self.db.commit()

        token = run(service.get_access_token(self.user.id, GMAIL))

        self.assertEqual(token, "access-2")
        self.assertEqual(client.refresh_calls, ["refresh-1"])

        row = (
            self.db.query(UserIntegration)
            .filter_by(user_id=self.user.id, service_name=GMAIL)
            .one()
        )
        # The refresh token survives a refresh response without one.
        self.assertEqual(
            self.cipher.decrypt(row.refresh_token), "refresh-1"
        )

    def test_missing_integration_raises_not_connected(self):
        service = self._service(FakeOAuthClient())

        with self.assertRaises(GoogleNotConnected):
            run(service.get_access_token(self.user.id, GOOGLE_DRIVE))

    def test_disconnect_revokes_and_clears_tokens(self):
        client = FakeOAuthClient()
        service = self._service(client)

        service.store_tokens(
            user_id=self.user.id,
            service_name=GMAIL,
            tokens=GoogleTokens(
                access_token="access-1",
                refresh_token="refresh-1",
                expires_at=datetime.now(timezone.utc)
                + timedelta(hours=1),
            ),
        )
        self.db.commit()

        self.assertTrue(
            run(service.disconnect(self.user.id, GMAIL))
        )

        row = (
            self.db.query(UserIntegration)
            .filter_by(user_id=self.user.id, service_name=GMAIL)
            .one()
        )

        self.assertEqual(client.revoked, ["refresh-1"])
        self.assertFalse(row.is_connected)
        self.assertIsNone(row.access_token)
        self.assertIsNone(row.refresh_token)
        self.assertEqual(service.connected_services(self.user.id), [])


# ---------------------------------------------------------
# Tool gating and execution
# ---------------------------------------------------------


class StubGoogleService:
    def __init__(self):
        self.calls = []

    async def gmail_search(self, query=None, max_results=10):
        self.calls.append(("gmail_search", query, max_results))
        return {"count": 0, "messages": []}

    async def gmail_message(self, message_id):
        raise GoogleNotConnected(GMAIL)


class GoogleToolsTest(unittest.TestCase):
    def test_tools_are_gated_by_connected_services(self):
        service = StubGoogleService()

        names = {
            spec.name
            for spec in build_google_tools(service, [GMAIL])
        }

        self.assertIn("gmail_search_messages", names)
        self.assertFalse(
            any(name.startswith("drive_") for name in names)
        )

    def test_no_tools_when_nothing_connected(self):
        self.assertEqual(
            build_google_tools(StubGoogleService(), []), []
        )

    def test_all_services_produce_tools(self):
        specs = build_google_tools(
            StubGoogleService(),
            [GMAIL, GOOGLE_CALENDAR, GOOGLE_DRIVE, GOOGLE_SHEETS],
        )

        prefixes = {spec.name.split("_")[0] for spec in specs}

        self.assertEqual(
            prefixes,
            {"gmail", "calendar", "drive", "sheets"},
        )

    def test_prompt_mentions_connected_services_only(self):
        prompt = google_tools_prompt([GMAIL])

        self.assertIn("Connected services: \U0001f4e7 Gmail.", prompt)
        self.assertIn("Not connected", prompt)
        self.assertIn("Google Drive", prompt.split("Not connected")[1])

    def test_prompt_without_connections(self):
        prompt = google_tools_prompt([])

        self.assertIn("/connect", prompt)


class ToolRegistryTest(unittest.TestCase):
    def test_result_is_json_encoded(self):
        service = StubGoogleService()
        registry = ToolRegistry(build_google_tools(service, [GMAIL]))

        payload = run(
            registry.execute(
                "gmail_search_messages",
                {"query": "from:bank", "max_results": 5},
            )
        )

        self.assertEqual(json.loads(payload)["count"], 0)
        self.assertEqual(
            service.calls, [("gmail_search", "from:bank", 5)]
        )

    def test_not_connected_is_reported_to_the_llm(self):
        registry = ToolRegistry(
            build_google_tools(StubGoogleService(), [GMAIL])
        )

        payload = json.loads(
            run(
                registry.execute(
                    "gmail_read_message", {"message_id": "abc"}
                )
            )
        )

        self.assertEqual(payload["error"], "not_connected")
        self.assertIn("/connect", payload["message"])

    def test_unknown_tool_is_reported(self):
        registry = ToolRegistry([])

        payload = json.loads(run(registry.execute("nope", {})))

        self.assertEqual(payload["error"], "unknown_tool")

    def test_handler_exceptions_do_not_propagate(self):
        async def boom(_arguments):
            raise RuntimeError("kaboom")

        registry = ToolRegistry(
            [
                ToolSpec(
                    name="boom",
                    description="",
                    parameters={"type": "object", "properties": {}},
                    handler=boom,
                )
            ]
        )

        payload = json.loads(run(registry.execute("boom", {})))

        self.assertEqual(payload["error"], "tool_failed")
        self.assertIn("kaboom", payload["message"])

    def test_timeout_is_reported(self):
        async def slow(_arguments):
            await asyncio.sleep(1)

        registry = ToolRegistry(
            [
                ToolSpec(
                    name="slow",
                    description="",
                    parameters={"type": "object", "properties": {}},
                    handler=slow,
                    timeout_seconds=0.01,
                )
            ]
        )

        payload = json.loads(run(registry.execute("slow", {})))

        self.assertEqual(payload["error"], "timeout")


# ---------------------------------------------------------
# Provider mapping helpers
# ---------------------------------------------------------


class GmailMappingTest(unittest.TestCase):
    def test_message_is_flattened(self):
        payload = {
            "id": "m1",
            "threadId": "t1",
            "snippet": "Your statement is ready",
            "labelIds": ["INBOX"],
            "internalDate": "1700000000000",
            "payload": {
                "headers": [
                    {"name": "From", "value": "bank@example.com"},
                    {"name": "Subject", "value": "Statement"},
                    {"name": "Date", "value": "Wed, 15 Nov 2023"},
                ],
                "mimeType": "text/plain",
                "body": {"data": "SGVsbG8gd29ybGQ="},
            },
        }

        message = gmail_provider._map_message(payload)

        self.assertEqual(message["id"], "m1")
        self.assertEqual(message["from"], "bank@example.com")
        self.assertEqual(message["subject"], "Statement")
        self.assertEqual(
            gmail_provider._extract_body(payload["payload"]),
            "Hello world",
        )

    def test_html_body_is_used_as_a_fallback(self):
        part = {
            "mimeType": "multipart/alternative",
            "parts": [
                {
                    "mimeType": "text/html",
                    "body": {"data": "PGI+SGk8L2I+IHRoZXJl"},
                }
            ],
        }

        self.assertEqual(
            gmail_provider._extract_body(part), "Hi there"
        )


class GoogleDataServiceTest(unittest.TestCase):
    """The 401 -> force refresh -> retry path."""

    class FakeTokenService:
        def __init__(self):
            self.tokens = ["stale-token", "fresh-token"]
            self.forced = []

        def connected_services(self, _user_id):
            return [GMAIL]

        async def get_access_token(
            self, _user_id, _service, force_refresh=False
        ):
            self.forced.append(force_refresh)
            return self.tokens[1 if force_refresh else 0]

    def setUp(self):
        self.token_service = self.FakeTokenService()
        self.service = google_service_module.GoogleDataService(
            db=None,
            user_id=7,
            token_service=self.token_service,
        )
        self.service.invalidate_cache()
        self.used_tokens = []

    def tearDown(self):
        self.service.invalidate_cache()

    def test_unauthorized_triggers_one_forced_refresh(self):
        async def flaky(token):
            self.used_tokens.append(token)

            if token == "stale-token":
                raise GoogleUnauthorized("token expired")

            return {"ok": True}

        result = run(
            self.service._call(
                GMAIL, flaky, cache_key=("unit-test", "401")
            )
        )

        self.assertEqual(result, {"ok": True})
        self.assertEqual(
            self.used_tokens, ["stale-token", "fresh-token"]
        )
        self.assertEqual(self.token_service.forced, [False, True])

    def test_results_are_cached_per_user_and_query(self):
        calls = []

        async def counted(token):
            calls.append(token)
            return {"value": len(calls)}

        first = run(
            self.service._call(
                GMAIL, counted, cache_key=("unit-test", "cache")
            )
        )
        second = run(
            self.service._call(
                GMAIL, counted, cache_key=("unit-test", "cache")
            )
        )

        self.assertEqual(first, second)
        self.assertEqual(len(calls), 1)


class NormalizeServiceTest(unittest.TestCase):
    def test_aliases(self):
        self.assertEqual(normalize_service("Email"), GMAIL)
        self.assertEqual(normalize_service("calendar"), GOOGLE_CALENDAR)
        self.assertEqual(normalize_service("Google Drive"), GOOGLE_DRIVE)
        self.assertEqual(normalize_service("sheets"), GOOGLE_SHEETS)
        self.assertEqual(normalize_service("gmail"), GMAIL)


if __name__ == "__main__":
    unittest.main()
