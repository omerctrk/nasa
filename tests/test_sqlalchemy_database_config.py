"""Unit tests for safe SQL Server engine configuration."""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.db.session import create_database_engine, create_database_url


def test_sql_server_url_is_constructed_without_connecting() -> None:
    settings = Settings(
        database_host="10.38.136.212",
        database_port=1433,
        database_name="AstraHealth",
        database_username="astra_collaborator",
        collab_db_password="test-password",
    )
    database_url = create_database_url(settings)
    assert database_url.drivername == "mssql+pyodbc"
    assert database_url.host == "10.38.136.212"
    assert database_url.port == 1433
    assert database_url.database == "AstraHealth"
    assert database_url.username == "astra_collaborator"
    assert database_url.query["driver"] == "ODBC Driver 18 for SQL Server"
    assert database_url.query["Encrypt"] == "yes"

    engine = create_database_engine(settings)
    assert engine.url.get_backend_name() == "mssql"


def test_trust_server_certificate_is_limited_to_development() -> None:
    settings = Settings(
        collab_db_password="test-password",
        database_environment="production",
        database_trust_server_certificate=True,
    )
    with pytest.raises(ValueError, match="development"):
        create_database_engine(settings)


def test_database_password_is_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("COLLAB_DB_PASSWORD", raising=False)
    with pytest.raises(ValueError, match="COLLAB_DB_PASSWORD"):
        create_database_url(Settings(_env_file=None))


def test_development_trust_certificate_is_added_to_url() -> None:
    settings = Settings(collab_db_password="test-password", database_trust_server_certificate=True)
    assert create_database_url(settings).query["TrustServerCertificate"] == "yes"


def test_collab_password_is_read_from_its_unprefixed_environment_variable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("COLLAB_DB_PASSWORD", "test-password")
    settings = Settings()
    assert settings.collab_db_password is not None
    assert settings.collab_db_password.get_secret_value() == "test-password"
