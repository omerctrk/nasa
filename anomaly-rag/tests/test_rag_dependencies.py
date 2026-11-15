"""Unit tests for RAG application-state dependencies."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from starlette.requests import Request

from app.dependencies.rag import (
    get_embedding_provider,
    get_knowledge_card_index,
    get_knowledge_card_index_service,
    get_knowledge_card_retrieval_service,
    get_qdrant_client,
)


def request_with_state(**values: object) -> Request:
    application = FastAPI()
    for name, value in values.items():
        setattr(application.state, name, value)
    return Request({"type": "http", "app": application})


def test_rag_dependencies_return_initialized_application_state() -> None:
    provider = object()
    client = object()
    index = object()
    index_service = object()
    retrieval_service = object()
    request = request_with_state(
        embedding_provider=provider,
        qdrant_client=client,
        knowledge_card_index=index,
        knowledge_card_index_service=index_service,
        knowledge_card_retrieval_service=retrieval_service,
    )

    assert get_embedding_provider(request) is provider
    assert get_qdrant_client(request) is client
    assert get_knowledge_card_index(request) is index
    assert get_knowledge_card_index_service(request) is index_service
    assert get_knowledge_card_retrieval_service(request) is retrieval_service


def test_rag_dependency_fails_clearly_when_state_is_missing() -> None:
    with pytest.raises(RuntimeError, match="qdrant_client"):
        get_qdrant_client(request_with_state())
