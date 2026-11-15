"""Independent explicit indexing operations for Knowledge Cards."""

from __future__ import annotations

from app.embeddings.base import EmbeddingProvider
from app.schemas.knowledge_card import KnowledgeCard
from app.vector_store.qdrant_knowledge_card_index import QdrantKnowledgeCardIndex


class KnowledgeCardIndexService:
    """Index, replace, or remove cards only when explicitly invoked."""

    def __init__(self, embedding_provider: EmbeddingProvider, index: QdrantKnowledgeCardIndex) -> None:
        self._embedding_provider = embedding_provider
        self._index = index

    def index_card(self, card: KnowledgeCard) -> None:
        """Create or replace a card vector without touching CRUD storage."""
        vector = self._embedding_provider.embed_passages([card.text])[0]
        self._index.ensure_collection()
        self._index.upsert_card(card, vector)

    def remove_card(self, card_id: str) -> None:
        """Remove an explicitly selected card vector."""
        self._index.ensure_collection()
        self._index.delete_card(card_id)
