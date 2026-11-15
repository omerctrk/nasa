"""Semantic Knowledge Card retrieval service."""

from __future__ import annotations

from app.embeddings.base import EmbeddingProvider
from app.schemas.retrieval import RetrievedKnowledgeCard
from app.vector_store.qdrant_knowledge_card_index import QdrantKnowledgeCardIndex


class KnowledgeCardRetrievalService:
    """Retrieve cards independently from local-LLM answer generation."""

    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        index: QdrantKnowledgeCardIndex,
        top_k: int,
        minimum_similarity_score: float,
    ) -> None:
        self._embedding_provider = embedding_provider
        self._index = index
        self._top_k = top_k
        self._minimum_similarity_score = minimum_similarity_score

    def search(self, query: str) -> list[RetrievedKnowledgeCard]:
        """Embed a query and return source-preserving semantic matches."""
        query_vector = self._embedding_provider.embed_query(query)
        self._index.ensure_collection()
        return self._index.search(
            query_vector=query_vector,
            top_k=self._top_k,
            minimum_similarity_score=self._minimum_similarity_score,
        )
