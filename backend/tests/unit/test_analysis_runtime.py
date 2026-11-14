from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI

from app.core.analysis_runtime import analysis_transaction, configure_analysis
from app.repositories.sqlalchemy_repository import SqlAlchemyRepository


def test_a3_missing_disables_persistence_and_still_documents_endpoints(monkeypatch):
    monkeypatch.setattr(SqlAlchemyRepository, "create_or_get_job", None)
    app = FastAPI()
    configure_analysis(app)
    assert app.state.analysis_service is None
    assert "/api/v1/analysis/jobs" in app.openapi()["paths"]


def test_delivered_a3_enables_real_analysis_service():
    app = FastAPI()
    configure_analysis(app)
    assert app.state.analysis_service is not None


def test_complete_a3_api_enables_real_service(monkeypatch):
    for method in ["create_or_get_job", "get_job", "request_retry"]:
        monkeypatch.setattr(SqlAlchemyRepository, method, lambda *args: None, raising=False)
    app = FastAPI()
    configure_analysis(app)
    assert app.state.analysis_service is not None


def test_real_transaction_factory_commits_on_exit_and_closes():
    events = []
    session = object()

    @contextmanager
    def begin():
        events.append("open")
        try:
            yield session
        except Exception:
            events.append("rollback")
            raise
        else:
            events.append("commit")
        finally:
            events.append("close")

    module = SimpleNamespace(SessionLocal=SimpleNamespace(begin=begin))
    with patch.dict("sys.modules", {"app.db.session": module}):
        with analysis_transaction() as repo:
            assert isinstance(repo, SqlAlchemyRepository) and repo.session is session
        assert events == ["open", "commit", "close"]
        events.clear()
        try:
            with analysis_transaction():
                raise RuntimeError("test")
        except RuntimeError:
            pass
        assert events == ["open", "rollback", "close"]
