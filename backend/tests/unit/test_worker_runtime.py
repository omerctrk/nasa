import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI

from app.core.worker_runtime import WORKER_REPOSITORY_METHODS, analysis_worker_lifespan, build_worker
from app.repositories.sqlalchemy_repository import SqlAlchemyRepository
from app.schemas.common import AnalysisModule


def settings():
    return SimpleNamespace(job_lease_seconds=120, job_lease_renew_seconds=30,
                           model_total_timeout_seconds=60, anomaly_auto_retries=1,
                           anomaly_retry_delay_seconds=2, worker_poll_seconds=1)


def test_missing_a3_and_pipeline_do_not_enable_worker():
    assert build_worker(settings(), None) is None
    assert build_worker(settings(), {}) is None


def test_repository_alone_does_not_enable_worker(monkeypatch):
    for name in WORKER_REPOSITORY_METHODS:
        monkeypatch.setattr(SqlAlchemyRepository, name, lambda *args: None, raising=False)
    assert build_worker(settings(), None) is None
    invalid = {module: object() for module in AnalysisModule}
    assert build_worker(settings(), invalid) is None


def test_complete_pipeline_and_repository_can_enable_worker(monkeypatch):
    for name in WORKER_REPOSITORY_METHODS:
        monkeypatch.setattr(SqlAlchemyRepository, name, lambda *args: None, raising=False)
    async def prepare(*args):
        return {}
    async def evaluate(*args):
        return {}
    pipeline = SimpleNamespace(prepare=prepare, evaluate=evaluate, persist=lambda *args: None)
    assert build_worker(settings(), {module: pipeline for module in AnalysisModule}) is not None


def test_sync_network_pipeline_is_not_enabled(monkeypatch):
    for name in WORKER_REPOSITORY_METHODS:
        monkeypatch.setattr(SqlAlchemyRepository, name, lambda *args: None, raising=False)
    pipeline = SimpleNamespace(prepare=lambda *args: {}, evaluate=lambda *args: {}, persist=lambda *args: None)
    assert build_worker(settings(), {module: pipeline for module in AnalysisModule}) is None


class LifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_missing_dependencies_start_no_background_task(self):
        app = FastAPI()
        with patch("app.core.worker_runtime.get_settings", return_value=settings()):
            async with analysis_worker_lifespan(app):
                self.assertIsNone(app.state.analysis_worker)

    async def test_worker_is_cancelled_on_application_exit(self):
        started, cancelled = asyncio.Event(), asyncio.Event()
        class Worker:
            async def run(self, stop):
                started.set()
                try:
                    await asyncio.Event().wait()
                finally:
                    cancelled.set()
        worker, app = Worker(), FastAPI()
        with patch("app.core.worker_runtime.get_settings", return_value=settings()), \
                patch("app.core.worker_runtime.build_worker", return_value=worker):
            async with analysis_worker_lifespan(app):
                await asyncio.wait_for(started.wait(), 1)
                self.assertIs(app.state.analysis_worker, worker)
            self.assertTrue(cancelled.is_set())
