"""Lifespan hook; never start a worker with missing A3/Ö4/Ö5/Ö6/Ö9 pieces."""

import asyncio
import inspect
from contextlib import asynccontextmanager

from app.core.analysis_runtime import analysis_transaction
from app.core.config import get_settings
from app.repositories.sqlalchemy_repository import SqlAlchemyRepository
from app.schemas.common import AnalysisModule
from app.workers.analysis import AnalysisWorker, WorkerSettings

WORKER_REPOSITORY_METHODS = (
    "claim_next_job", "renew_job_lease", "recover_expired_jobs", "reschedule_job",
    "save_input_snapshot", "finalize_job",
)


def build_worker(settings, pipelines):
    worker_settings = WorkerSettings(
        lease_seconds=settings.job_lease_seconds, renew_seconds=settings.job_lease_renew_seconds,
        model_timeout_seconds=settings.model_total_timeout_seconds,
        automatic_retries=settings.anomaly_auto_retries,
        retry_delay_seconds=settings.anomaly_retry_delay_seconds, poll_seconds=settings.worker_poll_seconds,
    )
    if not all(callable(getattr(SqlAlchemyRepository, name, None)) for name in WORKER_REPOSITORY_METHODS):
        return None
    if not pipelines or set(pipelines) != set(AnalysisModule):
        return None
    if not all(callable(getattr(pipeline, name, None))
               for pipeline in pipelines.values() for name in ("prepare", "evaluate", "persist")):
        return None
    if not all(inspect.iscoroutinefunction(pipeline.prepare)
               and inspect.iscoroutinefunction(pipeline.evaluate)
               and not inspect.iscoroutinefunction(pipeline.persist)
               for pipeline in pipelines.values()):
        return None
    return AnalysisWorker(analysis_transaction, pipelines, worker_settings)


@asynccontextmanager
async def analysis_worker_lifespan(app):
    worker = build_worker(get_settings(), getattr(app.state, "analysis_pipelines", None))
    app.state.analysis_worker = worker
    if worker is None:
        yield
        return
    stop = asyncio.Event()
    task = asyncio.create_task(worker.run(stop))
    try:
        yield
    finally:
        stop.set()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
