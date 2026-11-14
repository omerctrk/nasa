"""Knowledge Card persistence. Transactions belong to the calling service."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.knowledge import KnowledgeCard


class SqlAlchemyKnowledgeRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, card_id: str) -> KnowledgeCard | None:
        return self.session.get(KnowledgeCard, card_id)

    def list(self, limit: int, offset: int) -> list[KnowledgeCard]:
        return list(self.session.scalars(
            select(KnowledgeCard).order_by(KnowledgeCard.card_id).limit(limit).offset(offset)
        ))

    def add(self, card: KnowledgeCard) -> None:
        self.session.add(card)

    def delete(self, card: KnowledgeCard) -> None:
        self.session.delete(card)
