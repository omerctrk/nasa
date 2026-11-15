"""FastAPI application entry point for ASTRA HEALTH."""

from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.engine import Engine

from app.core.config import get_settings
from app.db.session import create_database_engine, create_session_factory, verify_database_connection
from app.embeddings.sentence_transformer_provider import SentenceTransformerEmbeddingProvider
from app.routers import health, knowledge_cards
from app.services.knowledge_card_index_service import KnowledgeCardIndexService
from app.services.retrieval_service import KnowledgeCardRetrievalService
from app.vector_store.qdrant_knowledge_card_index import (
    QdrantKnowledgeCardIndex,
    create_qdrant_client,
)


EXPECTED_EMBEDDING_DIMENSION = 768


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Own process-scoped resources and validate selected persistence on startup."""
    settings = get_settings()
    embedding_provider = SentenceTransformerEmbeddingProvider(
        settings.embedding_model_name
    )
    application.state.embedding_provider = embedding_provider
    application.state.qdrant_client = None
    application.state.knowledge_card_index = None
    application.state.knowledge_card_index_service = None
    application.state.knowledge_card_retrieval_service = None
    application.state.database_engine = None
    application.state.database_session_factory = None
    application.state.knowledge_card_repository = settings.knowledge_card_repository

    qdrant_client = None
    database_engine: Engine | None = None
    try:
        embedding_dimension = embedding_provider.dimension
        if embedding_dimension != EXPECTED_EMBEDDING_DIMENSION:
            raise RuntimeError(
                "Embedding model vector dimension does not match the required "
                f"{EXPECTED_EMBEDDING_DIMENSION}: received {embedding_dimension}."
            )

        qdrant_client = create_qdrant_client(settings.qdrant_url)
        qdrant_client.get_collections()
        knowledge_card_index = QdrantKnowledgeCardIndex(
            qdrant_client,
            settings.qdrant_collection_name,
            embedding_dimension,
        )
        knowledge_card_index.ensure_collection()
        application.state.qdrant_client = qdrant_client
        application.state.knowledge_card_index = knowledge_card_index
        application.state.knowledge_card_index_service = KnowledgeCardIndexService(
            embedding_provider,
            knowledge_card_index,
        )
        application.state.knowledge_card_retrieval_service = KnowledgeCardRetrievalService(
            embedding_provider,
            knowledge_card_index,
            top_k=settings.retrieval_top_k,
            minimum_similarity_score=settings.retrieval_min_similarity_score,
        )
    except Exception as error:
        if qdrant_client is not None:
            qdrant_client.close()
        application.state.embedding_provider = None
        raise RuntimeError(
            "Qdrant retrieval infrastructure could not be initialized. "
            "Check that Qdrant is running at the configured ASTRA_QDRANT_URL, "
            "the embedding model is available, and the collection uses 768 dimensions."
        ) from error

    if settings.knowledge_card_repository == "sqlserver":
        try:
            database_engine = create_database_engine(settings)
            verify_database_connection(database_engine)
            application.state.database_engine = database_engine
            application.state.database_session_factory = create_session_factory(database_engine)
        except Exception as error:
            if database_engine is not None:
                database_engine.dispose()
            if qdrant_client is not None:
                qdrant_client.close()
            raise RuntimeError(
                "SQL Server Knowledge Card repository could not be initialized. "
                "Check COLLAB_DB_PASSWORD, SQL authentication, network access, and development TLS settings."
            ) from error
    try:
        yield
    finally:
        if database_engine is not None:
            database_engine.dispose()
        if qdrant_client is not None:
            qdrant_client.close()
        application.state.database_engine = None
        application.state.database_session_factory = None
        application.state.knowledge_card_retrieval_service = None
        application.state.knowledge_card_index_service = None
        application.state.knowledge_card_index = None
        application.state.qdrant_client = None
        application.state.embedding_provider = None


def create_app() -> FastAPI:
    """Build the HTTP application without creating external connections."""
    settings = get_settings()
    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(health.router, prefix=settings.api_prefix)
    application.include_router(knowledge_cards.router, prefix=settings.api_prefix)
    return application


app = create_app()
