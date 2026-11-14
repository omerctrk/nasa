"""Public anomaly result read contract."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from pydantic import field_validator

from app.schemas.common import (
    AnomalyLevel, BaselineStatus, ContractModel, DataQualityStatus, Eye, ModuleScope,
)


class AnomalyResultOut(ContractModel):
    id: UUID
    astronaut_id: str
    mission_day: int | None
    created_at: datetime
    module_scope: ModuleScope
    measurement: str | None
    eye: Eye | None
    algorithm: str
    model_version: str | None
    anomaly_score: float | None
    is_anomaly: bool
    level: AnomalyLevel
    summary: str
    drivers_json: list[Any]
    baseline_status: BaselineStatus
    data_quality_status: DataQualityStatus
    recommendation: str
    data_cutoff_at: datetime

    @field_validator("created_at", "data_cutoff_at")
    @classmethod
    def utc_database_time(cls, value: datetime) -> datetime:
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
