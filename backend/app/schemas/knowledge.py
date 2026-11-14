"""Knowledge Card HTTP contract for the central SQL Server store."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import Field, StringConstraints

from app.schemas.common import ContractModel


def _text(max_length: int):
    return Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=max_length)]


CardId = _text(80)
Metric = _text(128)


class KnowledgeCardContent(ContractModel):
    type: _text(32)
    system: _text(64)
    metrics: list[Metric] = Field(max_length=256)
    direction: _text(16)
    text: _text(100_000)
    source: _text(512)
    url: _text(2048)
    locator: _text(512)


class KnowledgeCardCreate(KnowledgeCardContent):
    card_id: CardId


class KnowledgeCardOut(KnowledgeCardCreate):
    content_hash: str
    created_at: datetime
    updated_at: datetime
