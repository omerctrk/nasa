"""Ö2 HTTP contracts; internal snapshots/provider metadata never leave here."""

from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import ConfigDict, Field, field_validator

from app.repositories.records import JobRequestData
from app.schemas.common import (
    AnalysisModule, ContractModel, EvaluationStatus, JobState, ModuleScope,
)


class AnalysisModel(ContractModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class AnomalyJobRequest(AnalysisModel):
    module: Literal[AnalysisModule.ANOMALY]
    idempotency_key: UUID
    module_scope: ModuleScope

    def to_record(self) -> JobRequestData:
        return JobRequestData(module=self.module, module_scope=self.module_scope)


class SansJobRequest(AnalysisModel):
    module: Literal[AnalysisModule.SANS]
    idempotency_key: UUID
    session_id: Annotated[str, Field(strict=True, min_length=1, max_length=64)]

    @field_validator("session_id")
    @classmethod
    def normalize_session_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Oturum kimliği boş olamaz.")
        return normalized

    def to_record(self) -> JobRequestData:
        return JobRequestData(module=self.module, session_id=self.session_id)


AnalysisJobRequest = Annotated[AnomalyJobRequest | SansJobRequest, Field(discriminator="module")]


class RetryJobRequest(AnalysisModel):
    """No replacement inputs: retry always refers to the existing job."""


class JobAcceptedResponse(AnalysisModel):
    job_id: UUID
    module: AnalysisModule
    state: JobState
    status_url: str


class JobStatusResponse(AnalysisModel):
    job_id: UUID
    astronaut_id: str
    module: AnalysisModule
    state: JobState
    attempts: int = Field(ge=0)
    retry_cycle: int = Field(ge=0)
    evaluation_status: EvaluationStatus | None
    error_code: Annotated[str, Field(pattern=r"^[A-Z][A-Z0-9_]{0,39}$")] | None
    anomaly_result_id: UUID | None
    sans_analysis_id: int | None
    created_at: datetime
    updated_at: datetime

    @field_validator("created_at", "updated_at")
    @classmethod
    def utc_database_time(cls, value: datetime) -> datetime:
        # ops UTC DATETIME2 columns have no offset in pyodbc's Python result.
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
