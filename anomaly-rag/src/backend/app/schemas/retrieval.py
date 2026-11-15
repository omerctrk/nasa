"""Retrieval result schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RetrievedKnowledgeCard(BaseModel):
    """A source-preserving semantic retrieval result."""

    card_id: str
    score: float
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")
