"""Environment-based configuration for the FastAPI application."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings. Secrets belong in .env or deployment environment variables."""

    app_name: str = "ASTRA HEALTH API"
    app_version: str = "0.1.0"
    api_prefix: str = "/api"
    debug: bool = False
    cors_origins: list[str] = ["http://localhost:3000"]
    embedding_model_name: str = "intfloat/multilingual-e5-base"
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection_name: str = "astra_health_knowledge_cards"
    retrieval_top_k: int = Field(default=5, ge=1, le=50)
    retrieval_min_similarity_score: float = Field(default=0.0, ge=-1.0, le=1.0)
    database_host: str = "10.38.136.212"
    database_port: int = Field(default=1433, ge=1, le=65535)
    database_name: str = "AstraHealth"
    database_username: str = "astra_collaborator"
    database_driver: str = "ODBC Driver 18 for SQL Server"
    collab_db_password: SecretStr | None = Field(
        default=None,
        validation_alias="COLLAB_DB_PASSWORD",
        repr=False,
    )
    database_environment: Literal["development", "test", "production"] = "development"
    database_trust_server_certificate: bool = False
    knowledge_card_repository: Literal["memory", "sqlserver"] = "memory"

    model_config = SettingsConfigDict(
        env_prefix="ASTRA_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return one settings instance for the current process."""
    return Settings()
