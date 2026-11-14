import unittest
from contextlib import contextmanager
from threading import get_ident
from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI
from app.core.errors import install_error_handling
from fastapi.testclient import TestClient

from app.core.errors import ApiError
from app.core.security import (AuthSettings, PasswordManager, TokenCodec, current_user,
                               require_active_astronaut, require_ground_control)
from app.routers.auth import install_auth
from app.schemas.auth import CurrentUser
from tests.fakes.auth import FakeAuthRepository
from tests.fixtures.auth import make_auth_repository


def replace(record, **updates):
    return record.model_copy(update=updates)


class AuthApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.password_hash = PasswordManager().hash_password("test-only-password")

    def setUp(self):
        original = make_auth_repository()
        self.users = {UUID(int=n): replace(original.get_user_by_id(UUID(int=n)),
                                          password_hash=self.password_hash) for n in range(1, 7)}
        self.events = []
        self.settings = AuthSettings(jwt_secret="test-only-" + "x" * 48)
        self.profiles = [original.get_astronaut("A007"), original.get_astronaut("A008")]

        @contextmanager
        def factory():
            self.events.append(("open", get_ident()))
            try:
                yield FakeAuthRepository(self.users.values(), self.profiles)
            finally:
                self.events.append(("close", get_ident()))

        self.app = FastAPI()
        install_error_handling(self.app)
        install_auth(self.app, factory, self.settings)

        @self.app.get("/test/astronaut")
        def astronaut(user: Annotated[CurrentUser, Depends(require_active_astronaut)]):
            return {"astronaut_id": user.astronaut_id}

        @self.app.get("/test/ground")
        def ground(user: Annotated[CurrentUser, Depends(require_ground_control)]):
            return {"user_id": str(user.user_id)}

        @self.app.get("/test/owned/{astronaut_id}")
        def owned(astronaut_id: str, user: Annotated[CurrentUser, Depends(current_user)]):
            # Illustrates the resource scope check that data/job services must do.
            if user.astronaut_id != astronaut_id:
                raise ApiError(404, "NOT_FOUND", "Kayıt bulunamadı.")
            return {"astronaut_id": astronaut_id}

        self.client = TestClient(self.app, raise_server_exceptions=False)

    def tearDown(self):
        self.client.close()

    def bearer(self, name="astronaut"):
        response = self.client.post("/api/v1/auth/login", json={
            "email": f"{name}@example.test", "password": "test-only-password"})
        self.assertEqual(response.status_code, 200, response.text)
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    def test_login_me_and_context_thread_lifetime(self):
        headers = self.bearer()
        response = self.client.get("/api/v1/auth/me", headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(set(response.json()), {"user_id", "email", "role", "astronaut_id"})
        self.assertEqual(response.json()["astronaut_id"], "A007")
        self.assertNotIn(self.password_hash, response.text)
        for opening, closing in zip(self.events[::2], self.events[1::2]):
            self.assertEqual(opening[1], closing[1])
            self.assertNotEqual(opening[1], get_ident())

    def test_authentication_and_authorization(self):
        for headers in [{}, {"Authorization": "Bearer broken"}, {"Authorization": "Basic abc"}]:
            response = self.client.get("/api/v1/auth/me", headers=headers)
            self.assertEqual(response.status_code, 401)
            self.assertEqual(response.headers["www-authenticate"], "Bearer")
        astronaut, ground = self.bearer(), self.bearer("ground")
        self.assertEqual(self.client.get("/test/astronaut", headers=astronaut).status_code, 200)
        self.assertEqual(self.client.get("/test/ground", headers=astronaut).status_code, 403)
        self.assertEqual(self.client.get("/test/ground", headers=ground).status_code, 200)
        self.assertEqual(self.client.get("/test/astronaut", headers=ground).status_code, 403)
        self.assertEqual(self.client.get("/test/owned/A007", headers=astronaut).status_code, 200)
        self.assertEqual(self.client.get("/test/owned/A008", headers=astronaut).status_code, 404)

    def test_display_profile_cannot_use_live_dependency(self):
        token = TokenCodec(self.settings).issue(UUID(int=4))
        response = self.client.get("/test/astronaut", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"]["code"], "FORBIDDEN")

    def test_disabled_user_is_denied_with_existing_token(self):
        headers = self.bearer()
        self.users[UUID(int=1)] = replace(self.users[UUID(int=1)], is_active=False)
        self.assertEqual(self.client.get("/api/v1/auth/me", headers=headers).status_code, 403)

    def test_validation_does_not_echo_secret_or_input(self):
        response = self.client.post("/api/v1/auth/login", json={
            "email": "invalid", "password": {"sensitive": "DO-NOT-ECHO"},
            "role": "ROOT", "PRIVATE-EXTRA-KEY": "value"})
        self.assertEqual(response.status_code, 422)
        detail = response.json()["detail"]
        self.assertEqual(set(detail), {"code", "message", "trace_id", "fields"})
        self.assertEqual(response.headers["x-trace-id"], detail["trace_id"])
        self.assertNotIn("DO-NOT-ECHO", response.text)
        self.assertNotIn("ROOT", response.text)
        self.assertNotIn("input", response.text)

    def test_login_failures_have_safe_envelope(self):
        for email, password, expected in [("unknown@example.test", "wrong", 401),
                                         ("astronaut@example.test", "wrong", 401),
                                         ("inactive@example.test", "test-only-password", 403),
                                         ("display@example.test", "test-only-password", 403)]:
            response = self.client.post("/api/v1/auth/login", json={"email": email, "password": password})
            self.assertEqual(response.status_code, expected)
            self.assertEqual(set(response.json()), {"detail"})
            self.assertNotIn(password, response.text)

    def test_storage_failure_has_trace_without_sensitive_exception(self):
        @contextmanager
        def broken_factory():
            raise RuntimeError("SQL PASSWORD=DO-NOT-ECHO")
            yield
        self.app.state.auth_service._repositories = broken_factory
        with self.assertLogs("astra.errors", level="ERROR") as logs:
            response = self.client.post("/api/v1/auth/login", json={
                "email": "astronaut@example.test", "password": "test-only-password"})
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()["detail"]["code"], "INTERNAL_ERROR")
        self.assertNotIn("DO-NOT-ECHO", response.text + str(logs.output))
        self.assertIn(response.json()["detail"]["trace_id"], str(logs.output))

    def test_framework_errors_and_openapi(self):
        self.assertEqual(self.client.get("/missing").json()["detail"]["code"], "NOT_FOUND")
        self.assertEqual(self.client.get("/api/v1/auth/login").status_code, 405)
        schema = self.client.get("/openapi.json").json()
        self.assertIn("/api/v1/auth/login", schema["paths"])
        self.assertIn("/api/v1/auth/me", schema["paths"])
        with self.assertRaises(RuntimeError):
            install_auth(self.app, lambda: None, self.settings)
