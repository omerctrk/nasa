import unittest
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt

from app.core.errors import ApiError
from app.core.security import AuthSettings, PasswordManager, TokenCodec


class SecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.passwords = PasswordManager()
        cls.password_hash = cls.passwords.hash_password("  test-password  ")

    def setUp(self):
        self.now = datetime(2027, 1, 5, tzinfo=UTC)
        self.settings = AuthSettings(jwt_secret="test-only-" + "x" * 48)
        self.codec = TokenCodec(self.settings, lambda: self.now)

    def test_argon2_and_whitespace(self):
        self.assertTrue(self.password_hash.startswith("$argon2id$"))
        self.assertTrue(self.passwords.verify_password("  test-password  ", self.password_hash))
        self.assertFalse(self.passwords.verify_password("test-password", self.password_hash))
        self.assertFalse(self.passwords.verify_password("input", "malformed"))
        self.assertFalse(self.passwords.verify_password("input", None))

    def test_valid_token_and_unique_jti(self):
        first, second = self.codec.issue(UUID(int=1)), self.codec.issue(UUID(int=1))
        self.assertNotEqual(first, second)
        self.assertEqual(self.codec.decode_subject(first), UUID(int=1))
        payload = jwt.decode(first, options={"verify_signature": False})
        self.assertEqual(payload["exp"] - payload["iat"], 3600)
        self.assertEqual(set(payload), {"sub", "iat", "exp", "iss", "aud", "jti"})

    def test_expiry_boundary_without_waiting(self):
        token = self.codec.issue(UUID(int=1))
        self.now += timedelta(seconds=3599)
        self.codec.decode_subject(token)
        self.now += timedelta(seconds=1)
        with self.assertRaises(ApiError) as caught:
            self.codec.decode_subject(token)
        self.assertEqual(caught.exception.status_code, 401)

    def test_rejects_invalid_signed_claims(self):
        base = jwt.decode(self.codec.issue(UUID(int=1)), options={"verify_signature": False})
        variants = []
        for name in base:
            item = dict(base)
            item.pop(name)
            variants.append(item)
        for updates in [
            {"iss": "other"}, {"aud": "other"}, {"aud": [self.settings.jwt_audience]},
            {"sub": "bad"}, {"sub": 1}, {"jti": "bad"}, {"jti": 1},
            {"iat": int(self.now.timestamp()) + 1}, {"iat": True},
            {"exp": str(base["exp"])}, {"exp": base["iat"]},
        ]:
            variants.append(base | updates)
        for payload in variants:
            with self.subTest(payload_keys=tuple(payload)), self.assertRaises(ApiError):
                self.codec.decode_subject(jwt.encode(payload, self.settings.jwt_secret, algorithm="HS256"))

    def test_rejects_bad_signature_algorithm_and_encoding(self):
        payload = jwt.decode(self.codec.issue(UUID(int=1)), options={"verify_signature": False})
        tokens = ["broken", jwt.encode(payload, "y" * 64, algorithm="HS256"),
                  jwt.encode(payload, self.settings.jwt_secret, algorithm="HS384"),
                  jwt.encode(payload, key="", algorithm="none")]
        for token in tokens:
            with self.subTest(token_kind=token[:10]), self.assertRaises(ApiError):
                self.codec.decode_subject(token)

    def test_settings_fail_without_secret_and_do_not_print_it(self):
        with self.assertRaises(KeyError):
            AuthSettings.from_env({})
        for secret in ["", "short"]:
            with self.assertRaises(ValueError):
                AuthSettings(jwt_secret=secret)
        self.assertNotIn(self.settings.jwt_secret, repr(self.settings))
        self.assertEqual(AuthSettings.from_env({"JWT_SECRET": "z" * 64}).access_token_seconds, 3600)
