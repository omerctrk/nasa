"""Ö2: authorize scope, canonicalize requests and own short transactions.

The context factory commits on successful exit, rolls back on failure and closes
its Session in the calling thread. No worker/provider call belongs in this API.
"""

import hashlib
import json
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass

from uuid import UUID

from app.core.errors import ApiError
from app.repositories.errors import InvalidStateTransition, NotFound
from app.repositories.interfaces import JobApiRepository
from app.repositories.records import JobRecord, JobRequestData, JobScope
from app.schemas.analysis import (
    AnalysisJobRequest, JobAcceptedResponse, JobStatusResponse,
)
from app.schemas.common import API_PREFIX, CurrentUser, ErrorCode, JobState, Role

JobTransactionFactory = Callable[[], AbstractContextManager[JobApiRepository]]


def canonical_request_hash(request: JobRequestData) -> str:
    payload = json.dumps(request.model_dump(mode="json", exclude_none=True),
                         sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                         allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class JobSubmission:
    response: JobAcceptedResponse
    created: bool


class AnalysisService:
    def __init__(self, transactions: JobTransactionFactory) -> None:
        self._transactions = transactions

    @staticmethod
    def _scope(user: CurrentUser) -> JobScope:
        # Live profile/active account checks happen in require_active_astronaut.
        # Keep a service guard too, so non-HTTP callers cannot supply ground scope.
        if user.role != Role.ASTRONAUT or not user.astronaut_id:
            raise ApiError(403, ErrorCode.FORBIDDEN, "Aktif astronot yetkisi gereklidir.")
        return JobScope(user_id=user.user_id, role=user.role, astronaut_id=user.astronaut_id)

    @staticmethod
    def _owned(job: JobRecord | None, scope: JobScope) -> JobRecord:
        if job is None or job.astronaut_id != scope.astronaut_id:
            raise NotFound()
        return job

    @staticmethod
    def _accepted(job: JobRecord) -> JobAcceptedResponse:
        return JobAcceptedResponse(job_id=job.job_id, module=job.module, state=job.state,
                                   status_url=f"{API_PREFIX}/analysis/jobs/{job.job_id}")

    def create(self, user: CurrentUser, request: AnalysisJobRequest) -> JobSubmission:
        scope = self._scope(user)
        normalized = request.to_record()
        digest = canonical_request_hash(normalized)
        with self._transactions() as repo:
            result = repo.create_or_get_job(scope, request.idempotency_key, digest, normalized)
            job = self._owned(result.job, scope)
            if job.module != normalized.module or job.request != normalized:
                raise ApiError(500, ErrorCode.INTERNAL_ERROR)
            response = self._accepted(job)
        # Return only AFTER context exit, so commit failure cannot produce 202.
        return JobSubmission(response=response, created=result.created)

    def get(self, user: CurrentUser, job_id: UUID) -> JobStatusResponse:
        scope = self._scope(user)
        with self._transactions() as repo:
            job = self._owned(repo.get_job(job_id, scope), scope)
            response = JobStatusResponse.model_validate(job.model_dump(
                exclude={"request", "has_snapshot"}))
        return response

    def retry(self, user: CurrentUser, job_id: UUID) -> JobAcceptedResponse:
        scope = self._scope(user)
        with self._transactions() as repo:
            previous = self._owned(repo.get_job(job_id, scope), scope)
            if previous.state != JobState.FAILED:
                raise InvalidStateTransition()
            # Repository must implement a conditional/atomic FAILED -> QUEUED.
            # The preceding read alone does not protect concurrent retry calls.
            job = self._owned(repo.request_retry(job_id, scope), scope)
            if (job.job_id != previous.job_id or job.state != JobState.QUEUED
                    or job.request != previous.request):
                raise ApiError(500, ErrorCode.INTERNAL_ERROR)
            response = self._accepted(job)
        return response
