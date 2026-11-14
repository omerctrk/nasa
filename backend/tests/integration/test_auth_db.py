"""Real MSSQL acceptance; enabled only by RUN_DB_TESTS=1 after migration.

Temporary identities live in the existing rollback fixture. This is not A6 seed.
"""
from contextlib import contextmanager
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.core.errors import ApiError
from app.core.security import AuthSettings, PasswordManager, TokenCodec
from app.models import Astronaut, User
from app.repositories.sqlalchemy_repository import SqlAlchemyRepository
from app.schemas.auth import LoginRequest
from app.services.auth import AuthService


@pytest.fixture
def auth_case(db, astronaut):
    assert db.scalar(text("SELECT USER_NAME()")) == "astra_app"
    passwords = PasswordManager()
    password = "temporary-test-only-password"
    suffix = uuid4().hex
    astro_user = User(user_id=uuid4(), email=f"astro-{suffix}@example.test",
                      password_hash=passwords.hash_password(password), role="ASTRONAUT",
                      is_active=True, astronaut_id=astronaut)
    ground_user = User(user_id=uuid4(), email=f"ground-{suffix}@example.test",
                       password_hash=passwords.hash_password(password), role="GROUND_CONTROL",
                       is_active=True, astronaut_id=None)
    db.add_all([astro_user, ground_user])
    db.flush()

    @contextmanager
    def repositories():
        # Synchronous service test stays in the same thread as the rollback fixture.
        yield SqlAlchemyRepository(db)

    service = AuthService(repositories, passwords, TokenCodec(AuthSettings(jwt_secret="test-only-" + "x" * 48)))
    return service, astro_user, ground_user, password


def test_real_repository_login_and_current_user(auth_case):
    service, astro, ground, password = auth_case
    for record in [astro, ground]:
        result = service.login(LoginRequest(email=record.email.upper(), password=password))
        user = service.resolve_user(result.access_token)
        assert user.user_id == record.user_id
        assert user.astronaut_id == record.astronaut_id
        assert "password_hash" not in user.model_dump()


def test_real_repository_rechecks_disabled_and_display_profile(db, auth_case):
    service, astro, _, password = auth_case
    token = service.login(LoginRequest(email=astro.email, password=password)).access_token
    astro.is_active = False
    db.flush()
    with pytest.raises(ApiError) as caught:
        service.resolve_user(token)
    assert caught.value.status_code == 403
    astro.is_active = True
    profile = db.get(Astronaut, astro.astronaut_id)
    profile.is_display_only = True
    db.flush()
    with pytest.raises(ApiError) as caught:
        service.resolve_user(token, require_astronaut=True)
    assert caught.value.status_code == 403


def test_auth_account_has_no_evaluation_or_ddl_permissions(db):
    assert db.scalar(text("SELECT USER_NAME()")) == "astra_app"
    assert db.scalar(text("SELECT HAS_PERMS_BY_NAME('evaluation', 'SCHEMA', 'SELECT')")) == 0
    assert db.scalar(text("SELECT HAS_PERMS_BY_NAME(DB_NAME(), 'DATABASE', 'CREATE TABLE')")) == 0
    assert db.scalar(text("SELECT IS_MEMBER('db_owner')")) == 0
