"""Unit tests for SQLAlchemy-backed Knowledge Card persistence."""

from __future__ import annotations

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models import KnowledgeCardRecord
from app.repositories.knowledge_card_repository import CardAlreadyExistsError, CardNotFoundError
from app.repositories.sqlalchemy_knowledge_card_repository import SqlAlchemyKnowledgeCardRepository
from app.schemas.knowledge_card import KnowledgeCard


def card(card_id: str = "renal-risk-001", text: str = "Monitor hydration and renal markers.") -> KnowledgeCard:
    return KnowledgeCard(
        id=card_id,
        type="risk",
        system="renal",
        metrics=["heart_rate"],
        direction="up",
        text=text,
        source="NASA clinical guidance",
        url="https://example.org/cards/renal-risk-001",
        locator="Section 4",
    )


def repository() -> tuple[Session, SqlAlchemyKnowledgeCardRepository]:
    engine = create_engine("sqlite+pysqlite:///:memory:").execution_options(
        schema_translate_map={"dbo": None}
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    return session, SqlAlchemyKnowledgeCardRepository(session)


def test_knowledge_card_model_has_expected_persistent_columns() -> None:
    columns = {column.name for column in inspect(KnowledgeCardRecord).columns}
    assert columns == {
        "card_id",
        "type",
        "system",
        "metrics",
        "direction",
        "text",
        "source",
        "url",
        "locator",
        "content_hash",
        "created_at",
        "updated_at",
    }
    assert KnowledgeCardRecord.__table__.primary_key.columns.keys() == ["card_id"]


def test_sqlalchemy_repository_crud_and_content_hash() -> None:
    session, cards = repository()
    try:
        created = cards.create(card())
        assert created.id == "renal-risk-001"
        assert cards.get_by_id(created.id).metrics == ["heart_rate"]
        assert [item.id for item in cards.list_all()] == [created.id]

        updated = cards.update(card(text="Reassess hydration and renal markers."))
        assert updated.text == "Reassess hydration and renal markers."
        record = session.get(KnowledgeCardRecord, updated.id)
        assert record is not None
        assert len(record.content_hash) == 64

        cards.delete(updated.id)
        try:
            cards.get_by_id(updated.id)
        except CardNotFoundError:
            pass
        else:
            raise AssertionError("Deleted card should not be retrievable.")
    finally:
        session.close()


def test_sqlalchemy_repository_rejects_duplicate_card_id() -> None:
    session, cards = repository()
    try:
        cards.create(card())
        try:
            cards.create(card())
        except CardAlreadyExistsError:
            pass
        else:
            raise AssertionError("Duplicate card ID should raise CardAlreadyExistsError.")
    finally:
        session.close()
