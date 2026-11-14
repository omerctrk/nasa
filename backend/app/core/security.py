"""Password/JWT primitives and reusable FastAPI authorization dependencies."""

import secrets
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID, uuid4

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.concurrency import run_in_threadpool

from app.core.errors import ApiError
from app.schemas.auth import UserResponse
from app.schemas.common import CurrentUser, ErrorCode, Role


@dataclass(frozen=True, slots=True)
class AuthSettings:
    jwt_secret: str = field(repr=False)
    jwt_issuer: str = "astra-health"
    jwt_audience: str = "astra-health-api"
    access_token_seconds: int = 3600

    def __post_init__(self) -> None:
        if len(self.jwt_secret.encode("utf-8")) < 32:
            raise ValueError("JWT secret en az 32 bayt olmalıdır.")
        if not self.jwt_issuer.strip() or not self.jwt_audience.strip():
            raise ValueError("JWT issuer ve audience zorunludur.")
        if type(self.access_token_seconds) is not int or self.access_token_seconds <= 0:
            raise ValueError("Token süresi pozitif tam sayı olmalıdır.")

    @classmethod
    def from_env(cls, environ: Mapping[str, str]) -> "AuthSettings":
        # No default secret. Aybala's central config may construct this directly.
        return cls(
            jwt_secret=environ["JWT_SECRET"],
            jwt_issuer=environ.get("JWT_ISSUER", "astra-health"),
            jwt_audience=environ.get("JWT_AUDIENCE", "astra-health-api"),
            access_token_seconds=int(environ.get("ACCESS_TOKEN_SECONDS", "3600")),
        )


class PasswordManager:
    def __init__(self) -> None:
        self._hasher = PasswordHasher()  # Argon2id, library's supported defaults.
        self._dummy_hash = self.hash_password(secrets.token_urlsafe(32))

    def hash_password(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify_password(self, password: str, password_hash: str | None) -> bool:
        target = password_hash if password_hash is not None else self._dummy_hash
        try:
            valid = self._hasher.verify(target, password)
        except (InvalidHashError, VerificationError):
            return False
        return bool(valid and password_hash is not None)


def invalid_token() -> ApiError:
    return ApiError(401, ErrorCode.UNAUTHORIZED, "Geçerli bir erişim token'ı gereklidir.",
                    headers={"WWW-Authenticate": "Bearer"})


class TokenCodec:
    def __init__(self, settings: AuthSettings, clock: Callable[[], datetime] | None = None) -> None:
        self.settings = settings
        self._clock = clock or (lambda: datetime.now(UTC))

    def _now(self) -> int:
        now = self._clock()
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("Token saati timezone-aware olmalıdır.")
        return int(now.timestamp())

    def issue(self, user_id: UUID) -> str:
        now = self._now()
        return jwt.encode(
            {"sub": str(user_id), "iat": now,
             "exp": now + self.settings.access_token_seconds,
             "iss": self.settings.jwt_issuer, "aud": self.settings.jwt_audience,
             "jti": str(uuid4())},
            self.settings.jwt_secret, algorithm="HS256",
        )

    def decode_subject(self, token: str) -> UUID:
        try:
            claims = jwt.decode(
                token, self.settings.jwt_secret, algorithms=["HS256"],
                issuer=self.settings.jwt_issuer, audience=self.settings.jwt_audience,
                options={"require": ["sub", "iat", "exp", "iss", "aud", "jti"],
                         "strict_aud": True, "verify_exp": False, "verify_iat": False},
            )
            # One injectable clock for deterministic expiry tests. Do not coerce
            # strings/bools into NumericDate values.
            now = self._now()
            if type(claims["iat"]) is not int or type(claims["exp"]) is not int:
                raise ValueError("invalid NumericDate")
            if claims["iat"] > now or claims["exp"] <= now or claims["exp"] <= claims["iat"]:
                raise ValueError("invalid token time")
            UUID(claims["jti"])
            return UUID(claims["sub"])
        except (jwt.InvalidTokenError, ValueError, TypeError, AttributeError) as exc:
            raise invalid_token() from exc


_bearer = HTTPBearer(auto_error=False)


def get_auth_service(request: Request):
    service = getattr(request.app.state, "auth_service", None)
    if service is None:
        raise ApiError(500, ErrorCode.INTERNAL_ERROR, "Kimlik servisi henüz hazır değil.")
    return service


async def authenticated_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    service=Depends(get_auth_service),
) -> UserResponse:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise invalid_token()
    # Session is opened, read and closed inside this single worker operation.
    return await run_in_threadpool(service.resolve_user, credentials.credentials)


def current_user(user: Annotated[UserResponse, Depends(authenticated_user)]) -> CurrentUser:
    return CurrentUser(user_id=user.user_id, role=user.role, astronaut_id=user.astronaut_id)


async def require_active_astronaut(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    service=Depends(get_auth_service),
) -> CurrentUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise invalid_token()
    user = await run_in_threadpool(service.resolve_user, credentials.credentials, True)
    return CurrentUser(user_id=user.user_id, role=user.role, astronaut_id=user.astronaut_id)


def require_ground_control(user: Annotated[CurrentUser, Depends(current_user)]) -> CurrentUser:
    if user.role != Role.GROUND_CONTROL:
        raise ApiError(403, ErrorCode.FORBIDDEN, "Kule yetkisi gereklidir.")
    return user
