"""Keep ordinary unit tests independent from external process-scoped services."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app import main


class UnitTestEmbeddingProvider:
    """A startup-only embedding provider with the verified E5 vector size."""

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name

    @property
    def dimension(self) -> int:
        return 768


@pytest.fixture(autouse=True)
def isolate_external_lifespan_services(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch):
    """Avoid SQL Server, Qdrant, and model downloads in ordinary unit tests."""
    if request.node.get_closest_marker("integration"):
        yield
        return

    settings = SimpleNamespace(
        app_name="ASTRA HEALTH API",
        app_version="0.1.0",
        api_prefix="/api",
        debug=False,
        cors_origins=["http://localhost:3000"],
        embedding_model_name="intfloat/multilingual-e5-base",
        qdrant_url="http://localhost:6333",
        qdrant_collection_name="astra_health_knowledge_cards",
        retrieval_top_k=5,
        retrieval_min_similarity_score=0.0,
        knowledge_card_repository="memory",
    )
    client = Mock()
    client.collection_exists.return_value = False
    monkeypatch.setattr(main, "get_settings", lambda: settings)
    monkeypatch.setattr(main, "SentenceTransformerEmbeddingProvider", UnitTestEmbeddingProvider)
    monkeypatch.setattr(main, "create_qdrant_client", lambda _: client)
    yield
