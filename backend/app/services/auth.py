"""Auth orchestration. The repository context owns its Session in this thread."""

from collections.abc import Callable
from contextlib import AbstractContextManager

from app.core.errors import ApiError
from app.core.security import PasswordManager, TokenCodec, invalid_token
from app.repositories.interfaces import IdentityRepository
from app.repositories.records import UserRecord
from app.schemas.auth import LoginRequest, TokenResponse, UserResponse
from app.schemas.common import ErrorCode, Role

RepositoryFactory = Callable[[], AbstractContextManager[IdentityRepository]]


class AuthService:
    def __init__(self, repositories: RepositoryFactory, passwords: PasswordManager, tokens: TokenCodec) -> None:
        self._repositories = repositories
        self._passwords = passwords
        self._tokens = tokens

    @staticmethod
    def _validate_user(repo: IdentityRepository, user: UserRecord, *, require_astronaut: bool = False,
                       reject_display: bool = False) -> UserResponse:
        if not user.is_active:
            raise ApiError(403, ErrorCode.FORBIDDEN, "Hesap etkin değil.")
        if user.role == Role.ASTRONAUT:
            profile = repo.get_astronaut(user.astronaut_id) if user.astronaut_id else None
            if profile is None or profile.astronaut_id != user.astronaut_id:
                raise ApiError(403, ErrorCode.FORBIDDEN, "Astronot profil bağlantısı geçersiz.")
            if reject_display and profile.is_display_only:
                raise ApiError(403, ErrorCode.FORBIDDEN, "Gösterim profiline canlı erişim kapalı.")
        elif user.role != Role.GROUND_CONTROL or user.astronaut_id is not None:
            raise ApiError(403, ErrorCode.FORBIDDEN, "Hesap yetki bilgisi geçersiz.")
        if require_astronaut and user.role != Role.ASTRONAUT:
            raise ApiError(403, ErrorCode.FORBIDDEN, "Aktif astronot yetkisi gereklidir.")
        return UserResponse(user_id=user.user_id, email=user.email,
                            role=user.role, astronaut_id=user.astronaut_id)

    def login(self, request: LoginRequest) -> TokenResponse:
        with self._repositories() as repo:
            user = repo.get_user_by_email(request.email)
            # Unknown accounts still undergo Argon2 verification using a dummy hash.
            verified = self._passwords.verify_password(
                request.password.get_secret_value(), user.password_hash if user else None)
            if not verified or user is None:
                raise ApiError(401, ErrorCode.UNAUTHORIZED, "E-posta veya parola hatalı.",
                               headers={"WWW-Authenticate": "Bearer"})
            public_user = self._validate_user(repo, user, reject_display=True)
        return TokenResponse(access_token=self._tokens.issue(public_user.user_id),
                             expires_in=self._tokens.settings.access_token_seconds)

    def resolve_user(self, token: str, require_astronaut: bool = False) -> UserResponse:
        subject = self._tokens.decode_subject(token)
        with self._repositories() as repo:
            user = repo.get_user_by_id(subject)
            if user is None:
                raise invalid_token()
            return self._validate_user(repo, user, require_astronaut=require_astronaut,
                                       reject_display=require_astronaut)
