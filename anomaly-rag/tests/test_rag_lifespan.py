"""Unit coverage for Qdrant initialization in the FastAPI lifecycle."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app import main


class FakeEmbeddingProvider:
    def __init__(self, model_name: str) -> None:
        self.model_name = model_name

    @property
    def dimension(self) -> int:
        return 768


def settings(**overrides: object) -> SimpleNamespace:
    defaults: dict[str, object] = {
        "app_name": "ASTRA HEALTH API",
        "app_version": "0.1.0",
        "api_prefix": "/api",
        "debug": False,
        "cors_origins": ["http://localhost:3000"],
        "embedding_model_name": "intfloat/multilingual-e5-base",
        "qdrant_url": "http://localhost:6333",
        "qdrant_collection_name": "astra_health_knowledge_cards",
        "retrieval_top_k": 5,
        "retrieval_min_similarity_score": 0.0,
        "knowledge_card_repository": "memory",
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_lifespan_initializes_and_closes_qdrant_resources(monkeypatch: pytest.MonkeyPatch) -> None:
    client = Mock()
    client.collection_exists.return_value = False
    monkeypatch.setattr(main, "get_settings", lambda: settings())
    monkeypatch.setattr(main, "SentenceTransformerEmbeddingProvider", FakeEmbeddingProvider)
    monkeypatch.setattr(main, "create_qdrant_client", lambda _: client)
    application = main.create_app()

    with TestClient(application):
        assert application.state.qdrant_client is client
        assert application.state.knowledge_card_index is not None
        assert application.state.knowledge_card_index_service is not None
        assert application.state.knowledge_card_retrieval_service is not None
        client.get_collections.assert_called_once()
        assert client.create_collection.call_args.kwargs["vectors_config"].size == 768

    client.close.assert_called_once()
    assert application.state.qdrant_client is None


def test_lifespan_reports_qdrant_initialization_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    client = Mock()
    client.get_collections.side_effect = OSError("Qdrant unavailable")
    monkeypatch.setattr(main, "get_settings", lambda: settings())
    monkeypatch.setattr(main, "SentenceTransformerEmbeddingProvider", FakeEmbeddingProvider)
    monkeypatch.setattr(main, "create_qdrant_client", lambda _: client)
    application = main.create_app()

    with pytest.raises(RuntimeError, match="Qdrant retrieval infrastructure"):
        with TestClient(application):
            pass

    client.close.assert_called_once()


def test_lifespan_rejects_non_768_embedding_dimension(monkeypatch: pytest.MonkeyPatch) -> None:
    class WrongDimensionProvider(FakeEmbeddingProvider):
        @property
        def dimension(self) -> int:
            return 384

    client_factory = Mock()
    monkeypatch.setattr(main, "get_settings", lambda: settings())
    monkeypatch.setattr(main, "SentenceTransformerEmbeddingProvider", WrongDimensionProvider)
    monkeypatch.setattr(main, "create_qdrant_client", client_factory)
    application = main.create_app()

    with pytest.raises(RuntimeError, match="768"):
        with TestClient(application):
            pass

    client_factory.assert_not_called()
