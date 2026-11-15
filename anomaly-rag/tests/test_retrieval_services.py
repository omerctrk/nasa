from __future__ import annotations

from app.embeddings.base import EmbeddingProvider
from app.schemas.knowledge_card import KnowledgeCard
from app.schemas.retrieval import RetrievedKnowledgeCard
from app.services.knowledge_card_index_service import KnowledgeCardIndexService
from app.services.retrieval_service import KnowledgeCardRetrievalService


class FakeEmbeddingProvider(EmbeddingProvider):
    @property
    def dimension(self) -> int:
        return 3

    def load(self) -> None:
        pass

    def embed_passages(self, passages: list[str]) -> list[list[float]]:
        self.passages = passages
        return [[0.1, 0.2, 0.3]]

    def embed_query(self, query: str) -> list[float]:
        self.query = query
        return [0.4, 0.5, 0.6]


class FakeIndex:
    def __init__(self) -> None:
        self.collection_checks = 0
        self.indexed: tuple[KnowledgeCard, list[float]] | None = None
        self.deleted_card_id: str | None = None
        self.search_arguments: tuple[list[float], int, float] | None = None

    def ensure_collection(self) -> None:
        self.collection_checks += 1

    def upsert_card(self, card: KnowledgeCard, vector: list[float]) -> None:
        self.indexed = (card, vector)

    def delete_card(self, card_id: str) -> None:
        self.deleted_card_id = card_id

    def search(self, query_vector: list[float], top_k: int, minimum_similarity_score: float):
        self.search_arguments = (query_vector, top_k, minimum_similarity_score)
        return [RetrievedKnowledgeCard(card_id="resp-01", score=0.8, metadata={"source": "NASA"})]


def card() -> KnowledgeCard:
    return KnowledgeCard(
        id="resp-01",
        type="risk",
        system="respiratory",
        metrics=["spo2"],
        direction="down",
        text="Source-based respiratory information.",
        source="NASA Technical Brief",
        url="https://example.com/source",
        locator="Page 4",
    )


def test_index_service_explicitly_indexes_and_deletes_card() -> None:
    provider = FakeEmbeddingProvider()
    index = FakeIndex()
    service = KnowledgeCardIndexService(provider, index)  # type: ignore[arg-type]

    service.index_card(card())
    service.remove_card("resp-01")

    assert provider.passages == ["Source-based respiratory information."]
    assert index.indexed is not None
    assert index.deleted_card_id == "resp-01"
    assert index.collection_checks == 2


def test_retrieval_service_embeds_query_and_applies_configured_filters() -> None:
    provider = FakeEmbeddingProvider()
    index = FakeIndex()
    service = KnowledgeCardRetrievalService(
        provider,
        index,  # type: ignore[arg-type]
        top_k=3,
        minimum_similarity_score=0.55,
    )

    results = service.search("respiratory information")

    assert provider.query == "respiratory information"
    assert index.search_arguments == ([0.4, 0.5, 0.6], 3, 0.55)
    assert results[0].card_id == "resp-01"
