"""Connect auth to Aybala's real Session/repository without crossing threads."""

from contextlib import contextmanager

from fastapi import FastAPI

from app.core.config import Settings
from app.core.security import AuthSettings
from app.routers.auth import install_auth


@contextmanager
def auth_repository():
    # Import lazily; factory entry/read/close all run inside one worker thread.
    from app.db.session import SessionLocal
    from app.repositories.sqlalchemy_repository import SqlAlchemyRepository

    with SessionLocal() as session:
        yield SqlAlchemyRepository(session)


def configure_auth(app: FastAPI, settings: Settings) -> None:
    if settings.db_user != "astra_app":
        raise ValueError("API kimlik servisi astra_app SQL hesabıyla çalışmalıdır.")
    install_auth(app, auth_repository, AuthSettings(
        jwt_secret=settings.jwt_secret or "",
        jwt_issuer=settings.jwt_issuer,
        jwt_audience=settings.jwt_audience,
        access_token_seconds=settings.access_token_seconds,
    ))
