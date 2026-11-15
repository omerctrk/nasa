"""SQLAlchemy models for durable application data."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, String, Unicode, UnicodeText
from sqlalchemy.dialects import mssql
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


SQLSERVER_NVARCHAR_MAX = UnicodeText().with_variant(mssql.NVARCHAR(length=None), "mssql")
SQLSERVER_DATETIME2 = DateTime().with_variant(mssql.DATETIME2(), "mssql")


def utc_now() -> datetime:
    """Return a naive UTC timestamp compatible with SQL Server DATETIME2."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class KnowledgeCardRecord(Base):
    """Relational persistence record for a source-traceable Knowledge Card."""

    __tablename__ = "knowledge_cards"
    __table_args__ = {"schema": "dbo"}

    card_id: Mapped[str] = mapped_column(Unicode(80), primary_key=True)
    type: Mapped[str] = mapped_column(Unicode(32), nullable=False)
    system: Mapped[str] = mapped_column(Unicode(64), nullable=False)
    metrics_json: Mapped[str] = mapped_column("metrics", SQLSERVER_NVARCHAR_MAX, nullable=False)
    direction: Mapped[str] = mapped_column(Unicode(16), nullable=False)
    text: Mapped[str] = mapped_column(SQLSERVER_NVARCHAR_MAX, nullable=False)
    source: Mapped[str] = mapped_column(Unicode(500), nullable=False)
    url: Mapped[str] = mapped_column(Unicode(2048), nullable=False)
    locator: Mapped[str] = mapped_column(Unicode(500), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(SQLSERVER_DATETIME2, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        SQLSERVER_DATETIME2, default=utc_now, onupdate=utc_now, nullable=False
    )
