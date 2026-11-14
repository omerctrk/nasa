import unittest
from contextlib import contextmanager
from datetime import UTC, datetime
from threading import get_ident
from uuid import UUID

from app.core.errors import ApiError
from app.core.security import AuthSettings, PasswordManager, TokenCodec
from app.schemas.auth import LoginRequest
from app.schemas.common import Role
from app.services.auth import AuthService
from tests.fakes.auth import FakeAuthRepository
from tests.fixtures.auth import make_auth_repository


def replace(record, **updates):
    return record.model_copy(update=updates)


class AuthServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.passwords = PasswordManager()
        cls.password_hash = cls.passwords.hash_password("test-only-password")

    def setUp(self):
        original = make_auth_repository()
        self.users = {UUID(int=n): replace(original.get_user_by_id(UUID(int=n)),
                                          password_hash=self.password_hash) for n in range(1, 7)}
        self.profiles = [original.get_astronaut("A007"), original.get_astronaut("A008")]
        self.events = []
        self.tokens = TokenCodec(AuthSettings(jwt_secret="test-only-" + "x" * 48),
                                 lambda: datetime(2027, 1, 5, tzinfo=UTC))

        @contextmanager
        def factory():
            self.events.append(("open", get_ident()))
            try:
                yield FakeAuthRepository(self.users.values(), self.profiles)
            finally:
                self.events.append(("close", get_ident()))

        self.factory = factory
        self.service = AuthService(factory, self.passwords, self.tokens)

    def login(self, email, password="test-only-password"):
        return self.service.login(LoginRequest(email=email, password=password))

    def test_active_astronaut_and_ground_login(self):
        for name, role in [("astronaut", Role.ASTRONAUT), ("ground", Role.GROUND_CONTROL)]:
            token = self.login(f"{name}@example.test").access_token
            self.assertEqual(self.service.resolve_user(token).role, role)
        self.assertEqual(len(self.events), 8)
        for opening, closing in zip(self.events[::2], self.events[1::2]):
            self.assertEqual(opening[1], closing[1])

    def test_unknown_and_wrong_password_have_same_error(self):
        errors = []
        for email in ["unknown@example.test", "astronaut@example.test", "inactive@example.test"]:
            with self.assertRaises(ApiError) as caught:
                self.login(email, "wrong")
            errors.append((caught.exception.status_code, caught.exception.code, caught.exception.message))
        self.assertEqual(errors, [errors[0]] * 3)
        self.assertEqual(errors[0][0], 401)

    def test_inactive_display_unlinked_and_missing_profile_are_denied(self):
        for name in ["inactive", "display", "unlinked", "missing-profile"]:
            with self.subTest(name=name), self.assertRaises(ApiError) as caught:
                self.login(f"{name}@example.test")
            self.assertEqual(caught.exception.status_code, 403)
        self.assertEqual(len(self.events), 8)  # contexts close on error too

    def test_disabled_deleted_user_and_changed_role_are_read_again(self):
        token = self.login("astronaut@example.test").access_token
        self.users[UUID(int=1)] = replace(self.users[UUID(int=1)], is_active=False)
        with self.assertRaises(ApiError) as caught:
            self.service.resolve_user(token)
        self.assertEqual(caught.exception.code, "FORBIDDEN")
        self.users[UUID(int=1)] = replace(self.users[UUID(int=1)], is_active=True,
                                         role=Role.GROUND_CONTROL, astronaut_id=None)
        self.assertEqual(self.service.resolve_user(token).role, Role.GROUND_CONTROL)
        self.users.pop(UUID(int=1))
        with self.assertRaises(ApiError) as caught:
            self.service.resolve_user(token)
        self.assertEqual(caught.exception.status_code, 401)

    def test_live_astronaut_rejects_ground_and_display(self):
        for number in [2, 4]:
            with self.subTest(number=number), self.assertRaises(ApiError) as caught:
                self.service.resolve_user(self.tokens.issue(UUID(int=number)), True)
            self.assertEqual(caught.exception.status_code, 403)
        user = self.service.resolve_user(self.tokens.issue(UUID(int=1)), True)
        self.assertEqual(user.astronaut_id, "A007")

    def test_corrupt_hash_is_bad_credentials_not_crash(self):
        self.users[UUID(int=1)] = replace(self.users[UUID(int=1)], password_hash="corrupt")
        with self.assertRaises(ApiError) as caught:
            self.login("astronaut@example.test")
        self.assertEqual(caught.exception.code, "UNAUTHORIZED")

    def test_repository_failure_propagates(self):
        @contextmanager
        def broken_factory():
            raise RuntimeError("storage unavailable")
            yield
        service = AuthService(broken_factory, self.passwords, self.tokens)
        with self.assertRaises(RuntimeError):
            service.login(LoginRequest(email="a@example.test", password="input"))
