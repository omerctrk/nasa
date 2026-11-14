"""JobRepository'nin gerçek uygulaması (A3, sahip: Aybala).

Eşzamanlılık kuralları:
- Tekillik: (astronaut_id, idempotency_key) UNIQUE; çakışmada mevcut iş okunur.
- Sahiplenme: tek UPDATE + UPDLOCK/READPAST — iki işçi aynı işi alamaz, kilitli satır atlanır.
- Lease: her yazma `lease_token` ile koşullu UPDATE'tir; 0 satır = sahiplik kaybı.
- Zaman: hep DB saati (SYSUTCDATETIME), işçi makinesinin saati değil.
Commit yapılmaz (sözleşme §7).
"""
from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy import select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.analysis import AnalysisJob
from app.repositories.errors import (
    IdempotencyConflict,
    InvalidStateTransition,
    LeaseLost,
    NotFound,
    SnapshotConflict,
    ValidationFailed,
)
from app.repositories.records import (
    ClaimedJob,
    CreateJobResult,
    JobOutcome,
    JobRecord,
    JobRequestData,
    JobScope,
    RecoveredJob,
)
from app.repositories.sqlalchemy_results import to_json
from app.schemas.common import (
    AnalysisModule,
    EvaluationStatus,
    JobState,
    Role,
)

ACTIVE = (JobState.SYNCING.value, JobState.ANALYZING.value)
NOW = text("SYSUTCDATETIME()")


def _hex64(value: str, field: str) -> str:
    if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValidationFailed(f"{field} 64 karakterlik küçük harf SHA-256 hex olmalı")
    return value


def _job(row: AnalysisJob) -> JobRecord:
    return JobRecord(
        job_id=row.job_id,
        astronaut_id=row.astronaut_id,
        module=AnalysisModule(row.module),
        state=JobState(row.state),
        request=JobRequestData.model_validate_json(row.request_json),
        attempts=row.attempts,
        retry_cycle=row.retry_cycle,
        has_snapshot=row.input_snapshot_json is not None,
        evaluation_status=EvaluationStatus(row.evaluation_status) if row.evaluation_status else None,
        error_code=row.error_code,
        anomaly_result_id=row.anomaly_result_id,
        sans_analysis_id=row.sans_analysis_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _scoped(stmt, scope: JobScope):
    """Astronot yalnız kendi işini görür; kule iki demo profilinin işlerini görür."""
    if scope.role is Role.ASTRONAUT:
        return stmt.where(AnalysisJob.astronaut_id == scope.astronaut_id)
    return stmt


class SqlAlchemyJobRepository:
    def __init__(self, session: Session, anomaly_auto_retries: int | None = None,
                 anomaly_retry_delay_seconds: float | None = None) -> None:
        self.session = session
        self._retries = anomaly_auto_retries
        self._delay = anomaly_retry_delay_seconds

    # --- yardımcılar -------------------------------------------------------------

    def _retry_policy(self) -> tuple[int, int]:
        if self._retries is None or self._delay is None:
            from app.core.config import get_settings

            s = get_settings()
            self._retries = s.anomaly_auto_retries if self._retries is None else self._retries
            self._delay = s.anomaly_retry_delay_seconds if self._delay is None else self._delay
        return self._retries, int(self._delay * 1000)

    def _load(self, job_id: uuid.UUID) -> AnalysisJob | None:
        return self.session.scalars(
            select(AnalysisJob).where(AnalysisJob.job_id == job_id)
            .execution_options(populate_existing=True)
        ).one_or_none()

    def _owned(self, job_id: uuid.UUID, lease_token: uuid.UUID):
        return (
            AnalysisJob.job_id == job_id,
            AnalysisJob.lease_token == lease_token,
            AnalysisJob.state.in_(ACTIVE),
        )

    # --- JobRepository -------------------------------------------------------------

    def create_or_get_job(self, scope: JobScope, idempotency_key: uuid.UUID,
                          request_hash: str, request: JobRequestData) -> CreateJobResult:
        if scope.astronaut_id is None:
            raise ValidationFailed("Analiz işi yalnız astronot kapsamında oluşturulur")
        _hex64(request_hash, "request_hash")
        row = AnalysisJob(
            job_id=uuid.uuid4(),
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            module=request.module.value,
            request_json=request.model_dump_json(),
            astronaut_id=scope.astronaut_id,
        )
        try:
            with self.session.begin_nested():
                self.session.add(row)
        except IntegrityError:
            existing = self.session.scalars(
                select(AnalysisJob).where(
                    AnalysisJob.astronaut_id == scope.astronaut_id,
                    AnalysisJob.idempotency_key == idempotency_key,
                )
            ).one_or_none()
            if existing is None:
                raise  # FK vb. gerçek hata
            if existing.request_hash != request_hash:
                raise IdempotencyConflict(str(existing.job_id)) from None
            return CreateJobResult(job=_job(existing), created=False)
        return CreateJobResult(job=_job(self._load(row.job_id)), created=True)

    def get_job(self, job_id: uuid.UUID, scope: JobScope) -> JobRecord | None:
        row = self.session.scalars(
            _scoped(select(AnalysisJob).where(AnalysisJob.job_id == job_id), scope)
        ).one_or_none()
        return _job(row) if row else None

    def claim_next_job(self, lease_seconds: int) -> ClaimedJob | None:
        token = uuid.uuid4()
        claimed = self.session.execute(
            text(
                """
                WITH next_job AS (
                    SELECT TOP (1) * FROM ops.AnalysisJobs WITH (UPDLOCK, READPAST, ROWLOCK)
                    -- next_attempt_at DATETIME2(3)'e yuvarlanarak (bazen yukarı) yazılır; aynı hassasiyetle
                    -- karşılaştırılmazsa az önce oluşan iş 1 ms boyunca "gelecekte" kalır.
                    WHERE state = 'QUEUED' AND next_attempt_at <= CAST(SYSUTCDATETIME() AS datetime2(3))
                    ORDER BY next_attempt_at, created_at
                )
                UPDATE next_job
                SET state = 'SYNCING', lease_token = :token,
                    lease_until = DATEADD(second, :lease, SYSUTCDATETIME()),
                    attempts = attempts + 1, updated_at = SYSUTCDATETIME()
                OUTPUT inserted.job_id;
                """
            ),
            {"token": str(token), "lease": int(lease_seconds)},
        ).scalar_one_or_none()
        if claimed is None:
            return None
        row = self._load(uuid.UUID(str(claimed)))  # pyodbc ham SQL'de metin döndürebilir
        return ClaimedJob(
            job=_job(row),
            lease_token=token,
            lease_until=row.lease_until,
            input_snapshot=json.loads(row.input_snapshot_json) if row.input_snapshot_json else None,
            input_hash=row.input_hash,
        )

    def renew_job_lease(self, job_id: uuid.UUID, lease_token: uuid.UUID,
                        lease_seconds: int) -> bool:
        result = self.session.execute(
            update(AnalysisJob)
            .where(*self._owned(job_id, lease_token), AnalysisJob.lease_until > NOW)
            .values(lease_until=text(f"DATEADD(second, {int(lease_seconds)}, SYSUTCDATETIME())"),
                    updated_at=NOW)
            .execution_options(synchronize_session=False)
        )
        return result.rowcount == 1

    def recover_expired_jobs(self) -> list[RecoveredJob]:
        retries, delay_ms = self._retry_policy()
        rows = self.session.execute(
            text(
                """
                UPDATE ops.AnalysisJobs
                SET state = CASE WHEN module = 'anomaly' AND attempts <= :retries
                                 THEN 'QUEUED' ELSE 'FAILED' END,
                    next_attempt_at = CASE WHEN module = 'anomaly' AND attempts <= :retries
                                 THEN DATEADD(millisecond, :delay, SYSUTCDATETIME())
                                 ELSE next_attempt_at END,
                    error_code = CASE WHEN module = 'anomaly' AND attempts <= :retries
                                 THEN error_code ELSE 'LEASE_EXPIRED' END,
                    lease_token = NULL, lease_until = NULL, updated_at = SYSUTCDATETIME()
                OUTPUT inserted.job_id, deleted.state, inserted.state
                WHERE state IN ('SYNCING', 'ANALYZING') AND lease_until < SYSUTCDATETIME();
                """
            ),
            {"retries": retries, "delay": delay_ms},
        ).all()
        # SANS POST'u otomatik tekrarlanmaz: süresi dolan SANS işi doğrudan FAILED olur.
        return [
            RecoveredJob(job_id=uuid.UUID(str(r[0])), previous_state=JobState(r[1]), new_state=JobState(r[2]))
            for r in rows
        ]

    def save_input_snapshot(self, job_id: uuid.UUID, lease_token: uuid.UUID,
                            snapshot: dict[str, Any], input_hash: str) -> None:
        _hex64(input_hash, "input_hash")
        first = self.session.execute(
            update(AnalysisJob)
            .where(*self._owned(job_id, lease_token), AnalysisJob.input_hash.is_(None))
            .values(input_snapshot_json=to_json(snapshot), input_hash=input_hash,
                    state=JobState.ANALYZING.value, updated_at=NOW)
            .execution_options(synchronize_session=False)
        ).rowcount
        if first == 1:
            return
        row = self._load(job_id)
        if row is None or row.lease_token != lease_token or row.state not in ACTIVE:
            raise LeaseLost(str(job_id))
        if row.input_hash != input_hash:
            raise SnapshotConflict(str(job_id))  # dondurulmuş girdi ezilmez
        # Aynı snapshot (retry): yalnız aşama ilerler.
        self.session.execute(
            update(AnalysisJob).where(*self._owned(job_id, lease_token))
            .values(state=JobState.ANALYZING.value, updated_at=NOW)
            .execution_options(synchronize_session=False)
        )

    def finalize_job(self, job_id: uuid.UUID, lease_token: uuid.UUID,
                     outcome: JobOutcome) -> JobRecord:
        row = self._load(job_id)
        if row is None or row.lease_token != lease_token or row.state not in ACTIVE:
            raise LeaseLost(str(job_id))
        self._check_outcome(row.module, outcome)
        values: dict[str, Any] = {
            "state": outcome.state.value,
            "evaluation_status": outcome.evaluation_status.value if outcome.evaluation_status else None,
            "anomaly_result_id": outcome.anomaly_result_id,
            "sans_analysis_id": outcome.sans_analysis_id,
            "outcome_json": to_json(outcome.outcome),
            "error_code": outcome.error_code,
            "lease_token": None,
            "lease_until": None,
            "updated_at": NOW,
        }
        if outcome.provider_metadata is not None:
            values["provider_metadata_json"] = to_json(outcome.provider_metadata)
        done = self.session.execute(
            update(AnalysisJob).where(*self._owned(job_id, lease_token)).values(**values)
            .execution_options(synchronize_session=False)
        ).rowcount
        if done != 1:
            raise LeaseLost(str(job_id))
        return _job(self._load(job_id))

    def request_retry(self, job_id: uuid.UUID, scope: JobScope) -> JobRecord:
        stmt = (
            update(AnalysisJob)
            .where(AnalysisJob.job_id == job_id, AnalysisJob.state == JobState.FAILED.value)
            .values(state=JobState.QUEUED.value, retry_cycle=AnalysisJob.retry_cycle + 1,
                    attempts=0, next_attempt_at=NOW, error_code=None, evaluation_status=None,
                    outcome_json=None, updated_at=NOW)
            .execution_options(synchronize_session=False)
        )
        if scope.role is Role.ASTRONAUT:
            stmt = stmt.where(AnalysisJob.astronaut_id == scope.astronaut_id)
        if self.session.execute(stmt).rowcount == 1:
            return _job(self._load(job_id))  # snapshot korunur
        if self.get_job(job_id, scope) is None:
            raise NotFound(str(job_id))
        raise InvalidStateTransition("Yalnız FAILED iş tekrar denenebilir")

    # --- kurallar -------------------------------------------------------------------

    @staticmethod
    def _check_outcome(module: str, o: JobOutcome) -> None:
        """Şema §7: COMPLETED/evaluated → modüle uygun sonuç FK dolu;
        insufficient/invalid → iki FK de NULL ve outcome dolu."""
        if o.state is JobState.FAILED:
            if o.anomaly_result_id or o.sans_analysis_id:
                raise ValidationFailed("FAILED iş sonuç kimliği taşımaz")
            return
        if o.evaluation_status is None:
            raise ValidationFailed("COMPLETED iş evaluation_status taşır")
        if o.evaluation_status is EvaluationStatus.EVALUATED:
            want_anomaly = module == AnalysisModule.ANOMALY.value
            if want_anomaly and (o.anomaly_result_id is None or o.sans_analysis_id is not None):
                raise ValidationFailed("anomaly işi anomaly_result_id ile tamamlanır")
            if not want_anomaly and (o.sans_analysis_id is None or o.anomaly_result_id is not None):
                raise ValidationFailed("sans işi sans_analysis_id ile tamamlanır")
        else:
            if o.anomaly_result_id or o.sans_analysis_id or o.outcome is None:
                raise ValidationFailed("değerlendirilemeyen işte sonuç satırı yok, outcome dolu")
