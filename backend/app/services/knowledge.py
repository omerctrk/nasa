"""Knowledge Card CRUD and canonical content hashing."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.models.knowledge import KnowledgeCard
from app.repositories.sqlalchemy_knowledge import SqlAlchemyKnowledgeRepository
from app.schemas.common import ErrorCode
from app.schemas.knowledge import KnowledgeCardContent, KnowledgeCardCreate, KnowledgeCardOut


def _content(content: KnowledgeCardContent) -> dict:
    return content.model_dump(include={
        "type", "system", "metrics", "direction", "text", "source", "url", "locator",
    })


def _digest(content: dict) -> str:
    canonical = json.dumps(content, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _out(row: KnowledgeCard) -> KnowledgeCardOut:
    return KnowledgeCardOut(
        card_id=row.card_id, type=row.type, system=row.system,
        metrics=json.loads(row.metrics), direction=row.direction, text=row.text,
        source=row.source, url=row.url, locator=row.locator,
        content_hash=row.content_hash, created_at=_utc(row.created_at),
        updated_at=_utc(row.updated_at),
    )


def _missing() -> ApiError:
    return ApiError(404, ErrorCode.NOT_FOUND, "Knowledge Card bulunamadı.")


def list_cards(db: Session, limit: int, offset: int) -> list[KnowledgeCardOut]:
    return [_out(row) for row in SqlAlchemyKnowledgeRepository(db).list(limit, offset)]


def get_card(db: Session, card_id: str) -> KnowledgeCardOut:
    row = SqlAlchemyKnowledgeRepository(db).get(card_id)
    if row is None:
        raise _missing()
    return _out(row)


def create_card(db: Session, body: KnowledgeCardCreate) -> KnowledgeCardOut:
    values = _content(body)
    row = KnowledgeCard(
        card_id=body.card_id, metrics=json.dumps(values.pop("metrics"), ensure_ascii=False,
                                                separators=(",", ":")),
        content_hash=_digest(_content(body)), **values,
    )
    SqlAlchemyKnowledgeRepository(db).add(row)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ApiError(409, ErrorCode.INVALID_STATE_TRANSITION,
                       "Knowledge Card kimliği zaten kullanılıyor.") from exc
    db.refresh(row)
    return _out(row)


def replace_card(db: Session, card_id: str, body: KnowledgeCardContent) -> KnowledgeCardOut:
    repo = SqlAlchemyKnowledgeRepository(db)
    row = repo.get(card_id)
    if row is None:
        raise _missing()
    values = _content(body)
    for name, value in values.items():
        setattr(row, name, json.dumps(value, ensure_ascii=False, separators=(",", ":"))
                if name == "metrics" else value)
    row.content_hash = _digest(values)
    row.updated_at = func.sysutcdatetime()
    db.commit()
    db.refresh(row)
    return _out(row)


def delete_card(db: Session, card_id: str) -> None:
    repo = SqlAlchemyKnowledgeRepository(db)
    row = repo.get(card_id)
    if row is None:
        raise _missing()
    repo.delete(row)
    db.commit()
