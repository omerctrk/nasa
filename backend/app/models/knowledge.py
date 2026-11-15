"""Knowledge Card storage in the shared AstraHealth database (migration 0007)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, Index, NVARCHAR, VARCHAR, text as sql_text
from sqlalchemy.dialects.mssql import DATETIME2
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class KnowledgeCard(Base):
    __tablename__ = "knowledge_cards"
    __table_args__ = (
        CheckConstraint("ISJSON([metrics]) = 1", name="ck_knowledge_cards_metrics_json"),
        Index("ix_knowledge_cards_content_hash", "content_hash"),
        {"schema": "dbo"},
    )

    card_id: Mapped[str] = mapped_column(NVARCHAR(80), primary_key=True)
    type: Mapped[str] = mapped_column(NVARCHAR(32))
    system: Mapped[str] = mapped_column(NVARCHAR(64))
    metrics: Mapped[str] = mapped_column(NVARCHAR(None))
    direction: Mapped[str] = mapped_column(NVARCHAR(16))
    text: Mapped[str] = mapped_column(NVARCHAR(None))
    source: Mapped[str] = mapped_column(NVARCHAR(512))
    url: Mapped[str] = mapped_column(NVARCHAR(2048))
    locator: Mapped[str] = mapped_column(NVARCHAR(512))
    content_hash: Mapped[str] = mapped_column(VARCHAR(64))
    created_at: Mapped[datetime] = mapped_column(
        DATETIME2(), server_default=sql_text("SYSUTCDATETIME()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DATETIME2(), server_default=sql_text("SYSUTCDATETIME()")
    )
