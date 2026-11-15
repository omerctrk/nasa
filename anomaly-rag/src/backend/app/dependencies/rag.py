"""Dependencies exposing initialized RAG infrastructure to future routers."""

from __future__ import annotations

from fastapi import Request
from qdrant_client import QdrantClient

from app.embeddings.base import EmbeddingProvider
from app.services.knowledge_card_index_service import KnowledgeCardIndexService
from app.services.retrieval_service import KnowledgeCardRetrievalService
from app.vector_store.qdrant_knowledge_card_index import QdrantKnowledgeCardIndex


def _state_value(request: Request, attribute: str):
    value = getattr(request.app.state, attribute, None)
    if value is None:
        raise RuntimeError(f"RAG infrastructure is not initialized: missing application state '{attribute}'.")
    return value


def get_embedding_provider(request: Request) -> EmbeddingProvider:
    """Return the process-scoped, loaded embedding provider."""
    return _state_value(request, "embedding_provider")


def get_qdrant_client(request: Request) -> QdrantClient:
    """Return the process-scoped Qdrant client."""
    return _state_value(request, "qdrant_client")


def get_knowledge_card_index(request: Request) -> QdrantKnowledgeCardIndex:
    """Return the initialized Knowledge Card vector index."""
    return _state_value(request, "knowledge_card_index")


def get_knowledge_card_index_service(request: Request) -> KnowledgeCardIndexService:
    """Return explicit indexing operations for future orchestrators."""
    return _state_value(request, "knowledge_card_index_service")


def get_knowledge_card_retrieval_service(request: Request) -> KnowledgeCardRetrievalService:
    """Return semantic retrieval operations; no HTTP endpoint is exposed yet."""
    return _state_value(request, "knowledge_card_retrieval_service")
