"""Auth contracts; these models do not perform authentication."""

import re
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import ConfigDict, Field, SecretStr, field_validator, model_validator

from app.schemas.common import ContractModel, CurrentUser, Role


def normalize_email(value: str) -> str:
    """Shared demo login policy, also to be used by seed/repository adapters.

    Accept an ASCII email-shaped identifier, strip surrounding whitespace and
    lowercase it. This is not mailbox/deliverability verification.
    """
    normalized = value.strip().lower()
    if (
        len(normalized) > 254
        or not normalized.isascii()
        or re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", normalized) is None
    ):
        raise ValueError("Geçerli bir giriş e-postası girin.")
    return normalized


class AuthModel(ContractModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class LoginRequest(AuthModel):
    email: Annotated[str, Field(strict=True)]
    password: SecretStr

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return normalize_email(value)

    @field_validator("password", mode="before")
    @classmethod
    def validate_password(cls, value: object) -> object:
        # Do not strip: whitespace can be part of a valid password.
        if not isinstance(value, str) or not value:
            raise ValueError("Parola boş olmayan bir metin olmalıdır.")
        return value


class TokenResponse(AuthModel):
    access_token: Annotated[str, Field(min_length=1, strict=True, repr=False)]
    token_type: Literal["bearer"] = "bearer"
    expires_in: Annotated[int, Field(gt=0, strict=True)]


class ValidatedCurrentUser(CurrentUser):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    user_id: UUID
    role: Role
    astronaut_id: Annotated[str, Field(min_length=1, max_length=32, strict=True)] | None

    @model_validator(mode="after")
    def validate_role_binding(self) -> Self:
        if self.role == Role.ASTRONAUT and (
            self.astronaut_id is None or not self.astronaut_id.strip()
        ):
            raise ValueError("Astronot hesabının profil bağlantısı zorunludur.")
        if self.role == Role.GROUND_CONTROL and self.astronaut_id is not None:
            raise ValueError("Kule hesabının astronot bağlantısı olamaz.")
        return self


class UserResponse(ValidatedCurrentUser):
    email: Annotated[str, Field(strict=True)]

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return normalize_email(value)
