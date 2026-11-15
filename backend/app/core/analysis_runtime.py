"""Activate real job persistence only when Aybala's A3 repository exists."""

from contextlib import contextmanager

from fastapi import FastAPI

from app.repositories.sqlalchemy_repository import SqlAlchemyRepository
from app.routers.analysis import router
from app.schemas.common import API_PREFIX
from app.services.analysis import AnalysisService

API_REPOSITORY_METHODS = ("create_or_get_job", "get_job", "request_retry")


@contextmanager
def analysis_transaction():
    # Called in a sync endpoint's worker; no Session crosses threads.
    from app.db.session import SessionLocal

    with SessionLocal() as session, session.begin():
        yield SqlAlchemyRepository(session)


def configure_analysis(app: FastAPI) -> None:
    available = all(callable(getattr(SqlAlchemyRepository, method, None))
                    for method in API_REPOSITORY_METHODS)
    app.state.analysis_service = AnalysisService(analysis_transaction) if available else None
    app.include_router(router, prefix=API_PREFIX)
