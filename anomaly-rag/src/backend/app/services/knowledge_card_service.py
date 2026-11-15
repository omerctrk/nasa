"""Application service for Knowledge Card operations."""

from __future__ import annotations

from collections.abc import Iterator
from typing import cast

from fastapi import Request
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.repositories.sqlalchemy_knowledge_card_repository import SqlAlchemyKnowledgeCardRepository
from app.repositories.knowledge_card_repository import (
    InMemoryKnowledgeCardRepository,
    KnowledgeCardRepository,
)
from app.schemas.knowledge_card import KnowledgeCard


class KnowledgeCardService:
    """Keep API routes independent from the chosen persistence implementation."""

    def __init__(self, repository: KnowledgeCardRepository) -> None:
        self._repository = repository

    def create_card(self, card: KnowledgeCard) -> KnowledgeCard:
        return self._repository.create(card)

    def list_cards(self) -> list[KnowledgeCard]:
        return self._repository.list_all()

    def get_card(self, card_id: str) -> KnowledgeCard:
        return self._repository.get_by_id(card_id)

    def update_card(self, card: KnowledgeCard) -> KnowledgeCard:
        return self._repository.update(card)

    def delete_card(self, card_id: str) -> None:
        self._repository.delete(card_id)


_development_repository = InMemoryKnowledgeCardRepository()
_development_service = KnowledgeCardService(_development_repository)


def get_knowledge_card_service(request: Request) -> Iterator[KnowledgeCardService]:
    """Select the configured persistence backend for one API request.

    SQL Server sessions are transaction-scoped. The in-memory implementation
    remains the default, preserving local development and existing API tests.
    """
    settings = get_settings()
    if settings.knowledge_card_repository == "memory":
        yield _development_service
        return

    session_factory = cast(
        sessionmaker[Session] | None,
        getattr(request.app.state, "database_session_factory", None),
    )
    if session_factory is None:
        raise RuntimeError(
            "SQL Server Knowledge Card repository is selected but no database session factory is available."
        )

    session = session_factory()
    try:
        yield KnowledgeCardService(SqlAlchemyKnowledgeCardRepository(session))
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
