"""Test-only transactional Ö2 repository; never installed in the real app.

The lock models atomic unique-key/retry operations, not SQL Server behaviour.
Production atomicity remains an A3 DB acceptance requirement.
"""

from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import RLock
from uuid import UUID, uuid4

from app.repositories.errors import IdempotencyConflict, InvalidStateTransition, NotFound
from app.repositories.records import CreateJobResult, JobRecord, JobRequestData, JobScope
from app.schemas.common import JobState, Role


@dataclass
class StoredJob:
    record: JobRecord
    request_hash: str
    snapshot: dict | None = None
    input_hash: str | None = None


class FakeJobStore:
    def __init__(self):
        self.jobs: dict[UUID, StoredJob] = {}
        self.keys: dict[tuple[str, UUID], UUID] = {}
        self.lock = RLock()
        self.fail_next_commit = False
        self.commits = 0
        self.rollbacks = 0

    @contextmanager
    def transaction(self):
        with self.lock:
            before_jobs, before_keys = deepcopy(self.jobs), deepcopy(self.keys)
            try:
                yield FakeJobRepository(self)
                if self.fail_next_commit:
                    self.fail_next_commit = False
                    raise RuntimeError("test commit failure")
            except BaseException:
                self.jobs, self.keys = before_jobs, before_keys
                self.rollbacks += 1
                raise
            else:
                self.commits += 1

    def mark_failed(self, job_id: UUID, snapshot: dict | None = None, input_hash: str | None = None):
        """Fixture setup, not a worker implementation."""
        with self.lock:
            stored = self.jobs[job_id]
            stored.snapshot, stored.input_hash = deepcopy(snapshot), input_hash
            stored.record = stored.record.model_copy(update={
                "state": JobState.FAILED, "attempts": 2, "error_code": "MODEL_TIMEOUT",
                "has_snapshot": snapshot is not None,
            })


class FakeJobRepository:
    def __init__(self, store: FakeJobStore):
        self.store = store

    def get_job(self, job_id: UUID, scope: JobScope) -> JobRecord | None:
        stored = self.store.jobs.get(job_id)
        if (stored is None or scope.role != Role.ASTRONAUT
                or stored.record.astronaut_id != scope.astronaut_id):
            return None
        return stored.record.model_copy(deep=True)

    def create_or_get_job(self, scope: JobScope, idempotency_key: UUID,
                          request_hash: str, request: JobRequestData) -> CreateJobResult:
        if scope.role != Role.ASTRONAUT or not scope.astronaut_id:
            raise NotFound()
        key = (scope.astronaut_id, idempotency_key)
        existing_id = self.store.keys.get(key)
        if existing_id is not None:
            stored = self.store.jobs[existing_id]
            if stored.request_hash != request_hash:
                raise IdempotencyConflict()
            return CreateJobResult(job=stored.record.model_copy(deep=True), created=False)
        now = datetime.now(UTC)
        job = JobRecord(job_id=uuid4(), astronaut_id=scope.astronaut_id, module=request.module,
                        state=JobState.QUEUED, request=request, attempts=0, retry_cycle=0,
                        has_snapshot=False, evaluation_status=None, error_code=None,
                        anomaly_result_id=None, sans_analysis_id=None, created_at=now, updated_at=now)
        self.store.jobs[job.job_id] = StoredJob(job.model_copy(deep=True), request_hash)
        self.store.keys[key] = job.job_id
        return CreateJobResult(job=job, created=True)

    def request_retry(self, job_id: UUID, scope: JobScope) -> JobRecord:
        current = self.get_job(job_id, scope)
        if current is None:
            raise NotFound()
        if current.state != JobState.FAILED:
            raise InvalidStateTransition()
        updated = current.model_copy(update={
            "state": JobState.QUEUED, "retry_cycle": current.retry_cycle + 1,
            "attempts": 0, "error_code": None, "evaluation_status": None,
            "anomaly_result_id": None, "sans_analysis_id": None, "updated_at": datetime.now(UTC),
        })
        self.store.jobs[job_id].record = updated
        return updated.model_copy(deep=True)
