"""Tests for configured Knowledge Card repository selection."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from starlette.requests import Request

from app.core.config import get_settings
from app.services.knowledge_card_service import (
    KnowledgeCardService,
    _development_service,
    get_knowledge_card_service,
)


def request_with_state(**state: object) -> Request:
    application = FastAPI()
    for key, value in state.items():
        setattr(application.state, key, value)
    return Request({"type": "http", "app": application})


def test_memory_configuration_uses_existing_development_service(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ASTRA_KNOWLEDGE_CARD_REPOSITORY", "memory")
    get_settings.cache_clear()
    try:
        dependency = get_knowledge_card_service(request_with_state())
        assert next(dependency) is _development_service
        with pytest.raises(StopIteration):
            next(dependency)
    finally:
        get_settings.cache_clear()


def test_sqlserver_configuration_requires_initialized_session_factory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ASTRA_KNOWLEDGE_CARD_REPOSITORY", "sqlserver")
    get_settings.cache_clear()
    try:
        dependency = get_knowledge_card_service(request_with_state())
        with pytest.raises(RuntimeError, match="session factory"):
            next(dependency)
    finally:
        get_settings.cache_clear()
