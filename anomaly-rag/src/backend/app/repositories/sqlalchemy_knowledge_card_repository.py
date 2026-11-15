"""SQLAlchemy implementation of the Knowledge Card repository boundary."""

from __future__ import annotations

from hashlib import sha256
import json

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import KnowledgeCardRecord
from app.repositories.knowledge_card_repository import (
    CardAlreadyExistsError,
    CardNotFoundError,
)
from app.schemas.knowledge_card import KnowledgeCard


def serialize_metrics(metrics: list[str]) -> str:
    """Store metrics as deterministic JSON in an SQL Server NVARCHAR(MAX) column."""
    return json.dumps(metrics, ensure_ascii=False, separators=(",", ":"))


def content_hash_for(card: KnowledgeCard) -> str:
    """Create a stable fingerprint of the full source card content."""
    payload = card.model_dump(mode="json")
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(canonical.encode("utf-8")).hexdigest()


def record_to_schema(record: KnowledgeCardRecord) -> KnowledgeCard:
    """Convert a persisted record back to the validated API schema."""
    metrics = json.loads(record.metrics_json)
    if not isinstance(metrics, list) or not all(isinstance(metric, str) for metric in metrics):
        raise ValueError(f"Invalid metrics JSON stored for Knowledge Card '{record.card_id}'.")
    return KnowledgeCard.model_validate(
        {
            "id": record.card_id,
            "type": record.type,
            "system": record.system,
            "metrics": metrics,
            "direction": record.direction,
            "text": record.text,
            "source": record.source,
            "url": record.url,
            "locator": record.locator,
        }
    )


def apply_card(record: KnowledgeCardRecord, card: KnowledgeCard) -> None:
    """Copy validated card fields to a persistence record."""
    record.type = card.type
    record.system = card.system
    record.metrics_json = serialize_metrics(card.metrics)
    record.direction = card.direction
    record.text = card.text
    record.source = card.source
    record.url = str(card.url)
    record.locator = card.locator
    record.content_hash = content_hash_for(card)


class SqlAlchemyKnowledgeCardRepository:
    """Session-scoped SQLAlchemy repository; it does not commit transactions."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, card: KnowledgeCard) -> KnowledgeCard:
        record = KnowledgeCardRecord(card_id=card.id)
        apply_card(record, card)
        self._session.add(record)
        try:
            self._session.flush()
        except IntegrityError as error:
            self._session.rollback()
            raise CardAlreadyExistsError(card.id) from error
        return record_to_schema(record)

    def list_all(self) -> list[KnowledgeCard]:
        records = self._session.scalars(
            select(KnowledgeCardRecord).order_by(KnowledgeCardRecord.card_id)
        ).all()
        return [record_to_schema(record) for record in records]

    def get_by_id(self, card_id: str) -> KnowledgeCard:
        record = self._session.get(KnowledgeCardRecord, card_id)
        if record is None:
            raise CardNotFoundError(card_id)
        return record_to_schema(record)

    def update(self, card: KnowledgeCard) -> KnowledgeCard:
        record = self._session.get(KnowledgeCardRecord, card.id)
        if record is None:
            raise CardNotFoundError(card.id)
        apply_card(record, card)
        self._session.flush()
        return record_to_schema(record)

    def delete(self, card_id: str) -> None:
        record = self._session.get(KnowledgeCardRecord, card_id)
        if record is None:
            raise CardNotFoundError(card_id)
        self._session.delete(record)
        self._session.flush()
