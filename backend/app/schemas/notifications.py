"""Analiz sonucu ve kule alarm uçlarının istek/yanıt modelleri."""
from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from pydantic import Field

from app.schemas.common import (
    AlertStatus,
    AnalysisModule,
    AnomalyLevel,
    BaselineStatus,
    ContractModel,
    DataQualityStatus,
    ModuleScope,
    Severity,
)


class AnomalyResultOut(ContractModel):
    id: uuid.UUID
    astronaut_id: str
    mission_day: int | None
    created_at: dt.datetime
    module_scope: ModuleScope
    algorithm: str
    model_version: str | None
    is_anomaly: bool
    level: AnomalyLevel
    summary: str
    drivers: list[Any]  # eşik ihlalleri + {"type":"advice"} kart önerisi
    baseline_status: BaselineStatus
    data_quality_status: DataQualityStatus
    recommendation: str
    data_cutoff_at: dt.datetime


class AlertOut(ContractModel):
    alert_id: uuid.UUID
    astronaut_id: str
    module: AnalysisModule
    severity: Severity
    status: AlertStatus
    anomaly_result_id: uuid.UUID | None
    acknowledged_by: uuid.UUID | None
    acknowledged_at: dt.datetime | None
    resolved_by: uuid.UUID | None
    resolved_at: dt.datetime | None
    resolution_note: str | None
    created_at: dt.datetime


class ResolveIn(ContractModel):
    resolution_note: str = Field(min_length=1, max_length=1000)


class ReceiptResponse(ContractModel):
    recorded: bool
    event_id: uuid.UUID
