"""Auth router and explicit integration hook. There is no fake runtime default."""

from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, Response

from app.core.security import AuthSettings, PasswordManager, TokenCodec, authenticated_user, get_auth_service
from app.schemas.auth import LoginRequest, TokenResponse, UserResponse
from app.services.auth import AuthService, RepositoryFactory

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, response: Response,
          service: Annotated[AuthService, Depends(get_auth_service)]) -> TokenResponse:
    response.headers["Cache-Control"] = "no-store"
    return service.login(body)


@router.get("/me", response_model=UserResponse)
def me(response: Response, user: Annotated[UserResponse, Depends(authenticated_user)]) -> UserResponse:
    response.headers["Cache-Control"] = "no-store"
    return user


def install_auth(app: FastAPI, repositories: RepositoryFactory, settings: AuthSettings) -> None:
    """Call once from Aybala's main.py after central configuration validation.

    Each repository factory invocation must open/close its Session within the
    context. It must not return an existing request/thread's Session.
    """
    if getattr(app.state, "auth_service", None) is not None:
        raise RuntimeError("Auth servisi zaten kurulu.")
    app.state.auth_service = AuthService(repositories, PasswordManager(), TokenCodec(settings))
    app.include_router(router, prefix="/api/v1")
