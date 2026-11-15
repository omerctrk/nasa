"""Repository abstraction and development-only in-memory card storage."""

from __future__ import annotations

from threading import RLock
from typing import Protocol

from app.schemas.knowledge_card import KnowledgeCard


class CardAlreadyExistsError(Exception):
    """Raised when a repository already contains a requested card ID."""


class CardNotFoundError(Exception):
    """Raised when a requested card ID does not exist."""


class KnowledgeCardRepository(Protocol):
    """Persistence boundary to be implemented by SQL Server in a later phase."""

    def create(self, card: KnowledgeCard) -> KnowledgeCard: ...

    def list_all(self) -> list[KnowledgeCard]: ...

    def get_by_id(self, card_id: str) -> KnowledgeCard: ...

    def update(self, card: KnowledgeCard) -> KnowledgeCard: ...

    def delete(self, card_id: str) -> None: ...


class InMemoryKnowledgeCardRepository:
    """Thread-safe development storage that is cleared when the process exits."""

    def __init__(self) -> None:
        self._cards: dict[str, KnowledgeCard] = {}
        self._lock = RLock()

    def create(self, card: KnowledgeCard) -> KnowledgeCard:
        with self._lock:
            if card.id in self._cards:
                raise CardAlreadyExistsError(card.id)
            self._cards[card.id] = card.model_copy(deep=True)
            return card.model_copy(deep=True)

    def list_all(self) -> list[KnowledgeCard]:
        with self._lock:
            return [self._cards[card_id].model_copy(deep=True) for card_id in sorted(self._cards)]

    def get_by_id(self, card_id: str) -> KnowledgeCard:
        with self._lock:
            try:
                return self._cards[card_id].model_copy(deep=True)
            except KeyError as error:
                raise CardNotFoundError(card_id) from error

    def update(self, card: KnowledgeCard) -> KnowledgeCard:
        with self._lock:
            if card.id not in self._cards:
                raise CardNotFoundError(card.id)
            self._cards[card.id] = card.model_copy(deep=True)
            return card.model_copy(deep=True)

    def delete(self, card_id: str) -> None:
        with self._lock:
            if card_id not in self._cards:
                raise CardNotFoundError(card_id)
            del self._cards[card_id]
