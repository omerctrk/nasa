"""Lazy SQL Server engine and session-factory construction."""

from __future__ import annotations

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, URL
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings


def create_database_url(settings: Settings) -> URL:
    """Build a SQL Server URL in memory without exposing the password in config text."""
    if settings.collab_db_password is None:
        raise ValueError("COLLAB_DB_PASSWORD must be configured for SQL Server persistence.")

    query = {
        "driver": settings.database_driver,
        "Encrypt": "yes",
    }

    if settings.database_trust_server_certificate:
        if settings.database_environment != "development":
            raise ValueError(
                "TrustServerCertificate may only be enabled in the development environment."
            )
        query["TrustServerCertificate"] = "yes"

    return URL.create(
        drivername="mssql+pyodbc",
        username=settings.database_username,
        password=settings.collab_db_password.get_secret_value(),
        host=settings.database_host,
        port=settings.database_port,
        database=settings.database_name,
        query=query,
    )


def create_database_engine(settings: Settings) -> Engine:
    """Build a pool-managed SQL Server engine without opening a connection."""
    database_url = create_database_url(settings)

    return create_engine(database_url, pool_pre_ping=True)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Create a unit-of-work factory; callers retain transaction control."""
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def verify_database_connection(engine: Engine) -> None:
    """Open and validate a SQL Server connection without changing database state."""
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
