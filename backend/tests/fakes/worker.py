"""Transactional worker repository simulator; never used by production runtime."""

from contextlib import contextmanager
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.repositories.errors import InvalidStateTransition, LeaseLost, SnapshotConflict
from app.repositories.records import ClaimedJob, RecoveredJob
from app.schemas.common import AnalysisModule, JobState
from tests.fakes.analysis import FakeJobRepository, FakeJobStore


class WorkerJobStore(FakeJobStore):
    def __init__(self):
        super().__init__()
        self.clock = datetime.now(UTC)
        self.leases = {}
        self.scheduled = {}
        self.outcomes = {}
        self.results = {}
        self.renewals = 0
        self.transaction_depth = 0

    def advance(self, seconds):
        with self.lock:
            self.clock += timedelta(seconds=seconds)

    @contextmanager
    def transaction(self):
        with self.lock:
            extras = deepcopy((self.leases, self.scheduled, self.outcomes, self.results))
            try:
                with super().transaction():
                    self.transaction_depth += 1
                    try:
                        yield WorkerJobRepository(self)
                    finally:
                        self.transaction_depth -= 1
            except BaseException:
                self.leases, self.scheduled, self.outcomes, self.results = extras
                raise


class WorkerJobRepository(FakeJobRepository):
    def request_retry(self, job_id, scope):
        record = super().request_retry(job_id, scope)
        self.store.leases.pop(job_id, None)
        self.store.scheduled[job_id] = self.store.clock
        return record

    def _owned(self, job_id, lease_token):
        lease = self.store.leases.get(job_id)
        stored = self.store.jobs.get(job_id)
        if (stored is None or lease is None or lease[0] != lease_token
                or lease[1] <= self.store.clock
                or stored.record.state not in (JobState.SYNCING, JobState.ANALYZING)):
            raise LeaseLost()
        return stored

    def claim_next_job(self, lease_seconds):
        active_sans = {stored.record.astronaut_id for stored in self.store.jobs.values()
                       if stored.record.module == AnalysisModule.SANS
                       and stored.record.state in (JobState.SYNCING, JobState.ANALYZING)}
        for stored in sorted(self.store.jobs.values(), key=lambda s: (s.record.created_at, str(s.record.job_id))):
            job = stored.record
            if job.state != JobState.QUEUED or self.store.scheduled.get(job.job_id, self.store.clock) > self.store.clock:
                continue
            if job.module == AnalysisModule.SANS and job.astronaut_id in active_sans:
                continue
            token, until = uuid4(), self.store.clock + timedelta(seconds=lease_seconds)
            stored.record = job.model_copy(update={"state": JobState.SYNCING, "attempts": job.attempts + 1})
            self.store.leases[job.job_id] = token, until
            return ClaimedJob(job=stored.record.model_copy(deep=True), lease_token=token, lease_until=until,
                              input_snapshot=deepcopy(stored.snapshot), input_hash=stored.input_hash)
        return None

    def renew_job_lease(self, job_id, lease_token, lease_seconds):
        try:
            self._owned(job_id, lease_token)
        except LeaseLost:
            return False
        self.store.leases[job_id] = lease_token, self.store.clock + timedelta(seconds=lease_seconds)
        self.store.renewals += 1
        return True

    def save_input_snapshot(self, job_id, lease_token, snapshot, input_hash):
        stored = self._owned(job_id, lease_token)
        if stored.snapshot is not None:
            if stored.input_hash != input_hash or stored.snapshot != snapshot:
                raise SnapshotConflict()
        else:
            stored.snapshot, stored.input_hash = deepcopy(snapshot), input_hash
        stored.record = stored.record.model_copy(update={"state": JobState.ANALYZING, "has_snapshot": True})

    def reschedule_job(self, job_id, lease_token, delay_seconds, error_code, max_attempts=2):
        stored = self._owned(job_id, lease_token)
        if stored.record.module != AnalysisModule.ANOMALY or stored.record.attempts >= max_attempts:
            raise InvalidStateTransition()
        stored.record = stored.record.model_copy(update={"state": JobState.QUEUED, "error_code": error_code})
        self.store.leases.pop(job_id)
        self.store.scheduled[job_id] = self.store.clock + timedelta(seconds=delay_seconds)
        return stored.record.model_copy(deep=True)

    def recover_expired_jobs(self, max_attempts=2):
        recovered = []
        for job_id, (_, until) in list(self.store.leases.items()):
            if until > self.store.clock:
                continue
            stored = self.store.jobs[job_id]
            previous = stored.record.state
            unknown_sans = stored.record.module == AnalysisModule.SANS and previous == JobState.ANALYZING
            state = (JobState.QUEUED if not unknown_sans and stored.record.attempts < max_attempts
                     else JobState.FAILED)
            code = "SANS_RECONCILIATION_REQUIRED" if unknown_sans else "WORKER_LEASE_EXPIRED"
            stored.record = stored.record.model_copy(update={"state": state, "error_code": code})
            self.store.leases.pop(job_id)
            self.store.scheduled[job_id] = self.store.clock
            recovered.append(RecoveredJob(job_id=job_id, previous_state=previous, new_state=state))
        return recovered

    def finalize_job(self, job_id, lease_token, outcome):
        stored = self._owned(job_id, lease_token)
        stored.record = stored.record.model_copy(update={
            "state": outcome.state, "evaluation_status": outcome.evaluation_status,
            "error_code": outcome.error_code, "anomaly_result_id": outcome.anomaly_result_id,
            "sans_analysis_id": outcome.sans_analysis_id,
        })
        self.store.outcomes[job_id] = outcome.model_copy(deep=True)
        self.store.leases.pop(job_id)
        return stored.record.model_copy(deep=True)
