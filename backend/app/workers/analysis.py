"""Ö3 durable-job orchestration; DB persistence and processors are injected.

No SQLAlchemy Session/ORM object crosses an await or thread boundary. Each DB
operation enters its own transaction in the thread that executes that operation.
"""

import asyncio
import hashlib
import json
import logging
import math
from collections.abc import Callable, Mapping
from contextlib import AbstractContextManager
from copy import deepcopy
from dataclasses import dataclass
from typing import Protocol

from starlette.concurrency import run_in_threadpool

from app.repositories.errors import LeaseLost, SnapshotConflict
from app.repositories.interfaces import JobRepository
from app.repositories.records import ClaimedJob, JobOutcome, JobRecord
from app.schemas.common import AnalysisModule, EvaluationStatus, JobState

log = logging.getLogger("astra.worker")
Transactions = Callable[[], AbstractContextManager[JobRepository]]


class TransientModelError(Exception):
    """Provider adapter classified a transient connection failure."""


class PermanentModelError(Exception):
    """Authorization/request failure: retry will not repair this request."""


class InvalidModelOutput(Exception):
    """Provider output failed its schema/reference validation."""


class InvalidSnapshot(Exception):
    pass


class SansReconciliationRequired(Exception):
    pass


class AnalysisPipeline(Protocol):
    async def prepare(self, job: JobRecord) -> dict:
        """Ö4/Ö9: JSON-ready actual input, not a synthetic placeholder."""

    async def evaluate(self, job: JobRecord, snapshot: dict) -> object:
        """Ö5/Ö9: provider call + output validation, without an open transaction."""

    def persist(self, repo: JobRepository, job: JobRecord, result: object) -> JobOutcome:
        """Ö6: result/state/alerts/events writes using repo's SAME Session.

        Return COMPLETED outcome; worker finalizes job in the same transaction.
        This method must not commit, make external calls or return ORM objects.
        """


@dataclass(frozen=True)
class WorkerSettings:
    lease_seconds: int = 120
    renew_seconds: float = 30
    model_timeout_seconds: float = 60
    automatic_retries: int = 1
    retry_delay_seconds: float = 2
    poll_seconds: float = 1

    def __post_init__(self):
        values = (self.renew_seconds, self.model_timeout_seconds, self.retry_delay_seconds, self.poll_seconds)
        if type(self.lease_seconds) is not int or any(not math.isfinite(value) for value in values):
            raise ValueError("İşçi süreleri sonlu; lease süresi tam sayı olmalıdır.")
        if self.lease_seconds <= 0 or not 0 < self.renew_seconds < self.lease_seconds:
            raise ValueError("Lease süresi pozitif; yenileme aralığı lease'den kısa olmalıdır.")
        if self.model_timeout_seconds <= 0 or self.poll_seconds <= 0 or self.retry_delay_seconds < 0:
            raise ValueError("İşçi süreleri geçersiz.")
        if type(self.automatic_retries) is not int or self.automatic_retries not in (0, 1):
            raise ValueError("En fazla bir otomatik tekrar kullanılabilir.")

    @property
    def max_attempts(self) -> int:
        return self.automatic_retries + 1


def snapshot_hash(snapshot: dict) -> str:
    if not isinstance(snapshot, dict):
        raise InvalidSnapshot()
    try:
        payload = json.dumps(snapshot, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=False, allow_nan=False)
    except (ValueError, TypeError) as exc:
        raise InvalidSnapshot() from exc
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class AnalysisWorker:
    def __init__(self, transactions: Transactions,
                 pipelines: Mapping[AnalysisModule, AnalysisPipeline], settings: WorkerSettings):
        # claim_next_job has no module filter. Do not consume jobs for an absent pipeline.
        if set(pipelines) != set(AnalysisModule):
            raise ValueError("İşçi etkinleşmeden iki modülün pipeline'ı da bağlanmalıdır.")
        self.transactions, self.pipelines, self.settings = transactions, dict(pipelines), settings

    async def _db(self, operation):
        def execute():
            with self.transactions() as repo:
                return operation(repo)
        return await run_in_threadpool(execute)

    async def tick(self) -> bool:
        await self._db(lambda repo: repo.recover_expired_jobs(self.settings.max_attempts))
        claim = await self._db(lambda repo: repo.claim_next_job(self.settings.lease_seconds))
        if claim is None:
            return False
        await self._process(claim)
        return True

    def _renew(self, repo, claim: ClaimedJob):
        if not repo.renew_job_lease(claim.job.job_id, claim.lease_token, self.settings.lease_seconds):
            raise LeaseLost()

    async def _heartbeat(self, claim: ClaimedJob, lost: asyncio.Event):
        while True:
            await asyncio.sleep(self.settings.renew_seconds)
            try:
                await self._db(lambda repo: self._renew(repo, claim))
            except asyncio.CancelledError:
                raise
            except Exception:
                lost.set()
                return

    @staticmethod
    async def _guard(awaitable, lost: asyncio.Event):
        operation, watcher = asyncio.create_task(awaitable), asyncio.create_task(lost.wait())
        try:
            await asyncio.wait({operation, watcher}, return_when=asyncio.FIRST_COMPLETED)
            if lost.is_set():
                raise LeaseLost()
            return await operation
        finally:
            for task in (operation, watcher):
                if not task.done():
                    task.cancel()
            await asyncio.gather(operation, watcher, return_exceptions=True)

    @staticmethod
    def _validate_outcome(job: JobRecord, outcome: JobOutcome):
        if not isinstance(outcome, JobOutcome) or outcome.state != JobState.COMPLETED:
            raise InvalidModelOutput()
        refs = (outcome.anomaly_result_id, outcome.sans_analysis_id)
        if outcome.evaluation_status == EvaluationStatus.EVALUATED:
            expected = (True, False) if job.module == AnalysisModule.ANOMALY else (False, True)
            if tuple(ref is not None for ref in refs) != expected:
                raise InvalidModelOutput()
        elif outcome.evaluation_status in (EvaluationStatus.INSUFFICIENT_DATA, EvaluationStatus.INVALID_DATA):
            if any(ref is not None for ref in refs) or not outcome.outcome:
                raise InvalidModelOutput()
        else:
            raise InvalidModelOutput()

    async def _failed(self, claim: ClaimedJob, code: str):
        def finalize(repo):
            self._renew(repo, claim)
            repo.finalize_job(claim.job.job_id, claim.lease_token,
                              JobOutcome(state=JobState.FAILED, error_code=code))
        await self._db(finalize)

    async def _process(self, claim: ClaimedJob):
        lost = asyncio.Event()
        heartbeat = asyncio.create_task(self._heartbeat(claim, lost))
        phase = "PREPARING"
        pipeline = self.pipelines[claim.job.module]
        try:
            if claim.job.attempts < 1 or claim.job.attempts > self.settings.max_attempts:
                await self._failed(claim, "RETRY_EXHAUSTED")
                return
            if claim.job.state != JobState.SYNCING:
                raise InvalidSnapshot()
            snapshot = deepcopy(claim.input_snapshot)
            reused_snapshot = snapshot is not None
            if snapshot is None:
                if claim.job.has_snapshot or claim.input_hash is not None:
                    raise InvalidSnapshot()
                snapshot = await self._guard(pipeline.prepare(claim.job), lost)
                digest = snapshot_hash(snapshot)
            else:
                digest = snapshot_hash(snapshot)
                if digest != claim.input_hash:
                    raise InvalidSnapshot()
            # Copy before handing input to the provider. Provider mutation cannot
            # alter the frozen object saved by the repository.
            frozen = deepcopy(snapshot)

            def save(repo):
                self._renew(repo, claim)
                repo.save_input_snapshot(claim.job.job_id, claim.lease_token, frozen, digest)
            await self._db(save)
            if lost.is_set():
                raise LeaseLost()
            job = claim.job.model_copy(update={"state": JobState.ANALYZING, "has_snapshot": True})
            phase = "EVALUATING"
            async with asyncio.timeout(self.settings.model_timeout_seconds):
                evaluate = pipeline.evaluate
                if job.module == AnalysisModule.SANS and reused_snapshot:
                    # Manual retry resets attempts/error_code, so neither proves
                    # an earlier POST was safe. Always reconcile a reused SANS input.
                    evaluate = getattr(pipeline, "reconcile", None)
                    if not callable(evaluate):
                        raise SansReconciliationRequired()
                result = await self._guard(evaluate(job, deepcopy(frozen)), lost)
            phase = "PERSISTING"

            def persist(repo):
                self._renew(repo, claim)
                outcome = pipeline.persist(repo, job, result)
                self._validate_outcome(job, outcome)
                return repo.finalize_job(job.job_id, claim.lease_token, outcome)
            await self._db(persist)
        except asyncio.CancelledError:
            # Leave lease for durable restart recovery. SANS may have received its POST.
            raise
        except LeaseLost:
            log.info("code=LEASE_LOST job_id=%s", claim.job.job_id)
        except Exception as exc:
            # No provider exception text, response, token or snapshot is logged/stored.
            transient = phase == "EVALUATING" and isinstance(exc, (TransientModelError, TimeoutError))
            code = ("MODEL_TIMEOUT" if isinstance(exc, TimeoutError) else "MODEL_CONNECTION_ERROR")
            if isinstance(exc, SansReconciliationRequired):
                code = "SANS_RECONCILIATION_REQUIRED"
            elif phase == "EVALUATING" and claim.job.module == AnalysisModule.SANS and transient:
                code = "SANS_RECONCILIATION_REQUIRED"
            elif isinstance(exc, (InvalidSnapshot, SnapshotConflict)):
                code = "INPUT_SNAPSHOT_INVALID"
            elif isinstance(exc, InvalidModelOutput):
                code = "MODEL_OUTPUT_INVALID"
            elif isinstance(exc, PermanentModelError):
                code = "MODEL_REQUEST_REJECTED"
            elif not transient:
                code = {"PREPARING": "INPUT_PREPARATION_FAILED", "EVALUATING": "MODEL_FAILED",
                        "PERSISTING": "RESULT_PERSIST_FAILED"}[phase]
            try:
                if (transient and claim.job.module == AnalysisModule.ANOMALY
                        and claim.job.attempts < self.settings.max_attempts):
                    def reschedule(repo):
                        self._renew(repo, claim)
                        repo.reschedule_job(claim.job.job_id, claim.lease_token,
                                            self.settings.retry_delay_seconds, code,
                                            self.settings.max_attempts)
                    await self._db(reschedule)
                else:
                    await self._failed(claim, code)
            except LeaseLost:
                pass
            except Exception:
                # DB may be unavailable or commit outcome uncertain. Lease recovery
                # is the next safe action; never write a second unguarded result.
                log.error("code=WORKER_PERSIST_UNAVAILABLE job_id=%s", claim.job.job_id)
        finally:
            heartbeat.cancel()
            await asyncio.gather(heartbeat, return_exceptions=True)

    async def run(self, stop: asyncio.Event):
        while not stop.is_set():
            try:
                worked = await self.tick()
            except asyncio.CancelledError:
                raise
            except Exception:
                log.error("code=WORKER_STORAGE_UNAVAILABLE")
                worked = False
            if not worked and not stop.is_set():
                try:
                    await asyncio.wait_for(stop.wait(), self.settings.poll_seconds)
                except TimeoutError:
                    pass
