from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import FastAPI

from app.core.auth_runtime import auth_repository, configure_auth
from app.core.config import Settings
from app.repositories.interfaces import IdentityRepository
from app.repositories.sqlalchemy_repository import SqlAlchemyRepository
from app.schemas.auth import LoginRequest, UserResponse
from tests.fixtures.auth import make_auth_repository


def test_auth_uses_existing_sqlalchemy_repository_and_closes_session():
    session = object()
    events = []

    @contextmanager
    def session_factory():
        events.append("open")
        try:
            yield session
        finally:
            events.append("close")

    with patch.dict("sys.modules", {"app.db.session": SimpleNamespace(SessionLocal=session_factory)}):
        with auth_repository() as repo:
            assert isinstance(repo, SqlAlchemyRepository)
            assert isinstance(repo, IdentityRepository)
            assert repo.session is session
        assert events == ["open", "close"]


def test_real_runtime_configuration_requires_limited_account_and_secret():
    for changes in [{"jwt_secret": None}, {"db_user": "sa"}, {"jwt_secret": "short"}]:
        settings = Settings(_env_file=None, **({"db_password": "test-only", "db_user": "astra_app",
                                               "jwt_secret": "test-only-" + "x" * 48} | changes))
        with pytest.raises(ValueError):
            configure_auth(FastAPI(), settings)
    settings = Settings(_env_file=None, db_password="test-only", db_user="astra_app",
                        jwt_secret="test-only-" + "x" * 48)
    app = FastAPI()
    configure_auth(app, settings)
    assert {"/api/v1/auth/login", "/api/v1/auth/me"} <= set(app.openapi()["paths"])
    assert "test-only" not in repr(settings)


def test_public_user_cannot_leak_repository_hash():
    user = make_auth_repository().get_user_by_email("astronaut@example.test")
    assert "password_hash" not in user.model_dump()
    assert "TEST_ONLY_INVALID_HASH" not in repr(user)
    with pytest.raises(ValueError):
        UserResponse(**user.model_dump())
    request = LoginRequest(email=" ASTRONAUT@EXAMPLE.TEST ", password="  test  ")
    assert request.email == user.email
    assert request.password.get_secret_value() == "  test  "
