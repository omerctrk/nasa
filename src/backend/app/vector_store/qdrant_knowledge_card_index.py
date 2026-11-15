"""Qdrant adapter for independent Knowledge Card vector indexing."""

from __future__ import annotations

from uuid import NAMESPACE_URL, uuid5

from qdrant_client import QdrantClient, models

from app.schemas.knowledge_card import KnowledgeCard
from app.schemas.retrieval import RetrievedKnowledgeCard


def point_id_for_card(card_id: str) -> str:
    """Produce a deterministic Qdrant-compatible UUID without losing card_id."""
    return str(uuid5(NAMESPACE_URL, f"astra-health/knowledge-card/{card_id}"))


class QdrantKnowledgeCardIndex:
    """Store and retrieve card vectors while preserving source metadata payloads."""

    def __init__(self, client: QdrantClient, collection_name: str, vector_dimension: int) -> None:
        if vector_dimension <= 0:
            raise ValueError("vector_dimension must be positive")
        self._client = client
        self._collection_name = collection_name
        self._vector_dimension = vector_dimension

    def ensure_collection(self) -> None:
        """Create the collection or verify its existing vector dimension."""
        if not self._client.collection_exists(self._collection_name):
            self._client.create_collection(
                collection_name=self._collection_name,
                vectors_config=models.VectorParams(
                    size=self._vector_dimension,
                    distance=models.Distance.COSINE,
                ),
            )
            return

        collection = self._client.get_collection(self._collection_name)
        vectors = collection.config.params.vectors
        existing_dimension = vectors.size if hasattr(vectors, "size") else vectors["size"]
        if existing_dimension != self._vector_dimension:
            raise ValueError(
                "Qdrant collection vector dimension does not match the active embedding model: "
                f"collection={existing_dimension}, model={self._vector_dimension}."
            )

    def upsert_card(self, card: KnowledgeCard, vector: list[float]) -> None:
        """Insert or replace one card vector under its deterministic point ID."""
        if len(vector) != self._vector_dimension:
            raise ValueError(
                f"Embedding dimension mismatch: expected {self._vector_dimension}, got {len(vector)}."
            )
        payload = {
            "card_id": card.id,
            "type": card.type,
            "system": card.system,
            "metrics": card.metrics,
            "direction": card.direction,
            "text": card.text,
            "source": card.source,
            "url": str(card.url),
            "locator": card.locator,
        }
        self._client.upsert(
            collection_name=self._collection_name,
            wait=True,
            points=[models.PointStruct(id=point_id_for_card(card.id), vector=vector, payload=payload)],
        )

    def delete_card(self, card_id: str) -> None:
        """Remove a card vector by the deterministic ID derived from card_id."""
        self._client.delete(
            collection_name=self._collection_name,
            points_selector=models.PointIdsList(points=[point_id_for_card(card_id)]),
            wait=True,
        )

    def search(
        self,
        query_vector: list[float],
        top_k: int,
        minimum_similarity_score: float,
    ) -> list[RetrievedKnowledgeCard]:
        """Run cosine similarity search while preserving Qdrant payload metadata."""
        if len(query_vector) != self._vector_dimension:
            raise ValueError(
                f"Query vector dimension mismatch: expected {self._vector_dimension}, got {len(query_vector)}."
            )
        response = self._client.query_points(
            collection_name=self._collection_name,
            query=query_vector,
            limit=top_k,
            score_threshold=minimum_similarity_score,
            with_payload=True,
        )
        points = response.points if hasattr(response, "points") else response
        results: list[RetrievedKnowledgeCard] = []
        for point in points:
            payload = dict(point.payload or {})
            card_id = str(payload.pop("card_id", point.id))
            results.append(
                RetrievedKnowledgeCard(card_id=card_id, score=float(point.score), metadata=payload)
            )
        return results


def create_qdrant_client(url: str) -> QdrantClient:
    """Create a configured client without checking service availability yet."""
    return QdrantClient(url=url)
