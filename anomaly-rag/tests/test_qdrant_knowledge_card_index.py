from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.schemas.knowledge_card import KnowledgeCard
from app.vector_store.qdrant_knowledge_card_index import QdrantKnowledgeCardIndex, point_id_for_card


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


def test_collection_is_created_with_embedding_dimension() -> None:
    client = Mock()
    client.collection_exists.return_value = False
    index = QdrantKnowledgeCardIndex(client, "cards", 3)

    index.ensure_collection()

    assert client.create_collection.call_args.kwargs["collection_name"] == "cards"
    assert client.create_collection.call_args.kwargs["vectors_config"].size == 3


def test_existing_collection_dimension_must_match_model() -> None:
    client = Mock()
    client.collection_exists.return_value = True
    client.get_collection.return_value = SimpleNamespace(
        config=SimpleNamespace(params=SimpleNamespace(vectors=SimpleNamespace(size=2)))
    )
    index = QdrantKnowledgeCardIndex(client, "cards", 3)

    with pytest.raises(ValueError, match="dimension"):
        index.ensure_collection()


def test_upsert_and_delete_keep_card_id_in_payload() -> None:
    client = Mock()
    index = QdrantKnowledgeCardIndex(client, "cards", 3)

    index.upsert_card(card(), [0.1, 0.2, 0.3])
    index.delete_card("resp-01")

    point = client.upsert.call_args.kwargs["points"][0]
    assert point.id == point_id_for_card("resp-01")
    assert point.payload["card_id"] == "resp-01"
    assert client.delete.call_args.kwargs["points_selector"].points == [point_id_for_card("resp-01")]


def test_search_returns_card_id_score_and_metadata() -> None:
    client = Mock()
    client.query_points.return_value = SimpleNamespace(
        points=[
            SimpleNamespace(
                id=point_id_for_card("resp-01"),
                score=0.82,
                payload={"card_id": "resp-01", "system": "respiratory", "source": "NASA"},
            )
        ]
    )
    index = QdrantKnowledgeCardIndex(client, "cards", 3)

    results = index.search([0.1, 0.2, 0.3], top_k=5, minimum_similarity_score=0.4)

    assert results[0].card_id == "resp-01"
    assert results[0].score == 0.82
    assert results[0].metadata == {"system": "respiratory", "source": "NASA"}
    assert client.query_points.call_args.kwargs["score_threshold"] == 0.4
