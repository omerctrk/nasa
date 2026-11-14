"""anomaly.anomaly_results (A2) ve ops.AnalysisJobs (A3).

Sonuç satırı yalnız değerlendirme yapıldığında yazılır; insufficient_data/invalid_data
durumunda satır oluşmaz (iş outcome_json'unda kalır). anomaly_score bu demoda NULL.
"""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import (
    CHAR,
    Boolean,
    CheckConstraint,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Unicode,
    UnicodeText,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.mssql import DATETIME2
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AnomalyResult(Base):
    __tablename__ = "anomaly_results"
    __table_args__ = (
        CheckConstraint(
            "module_scope IN ('physiological','behavioral','sans','combined')",
            name="module_scope_valid",
        ),
        CheckConstraint("level IN ('normal','watch','review')", name="level_valid"),
        CheckConstraint(
            "baseline_status IN ('insufficient_data','provisional','ready')",
            name="baseline_status_valid",
        ),
        CheckConstraint(
            "data_quality_status IN ('valid','low_quality','missing_data')",
            name="data_quality_status_valid",
        ),
        CheckConstraint("ISJSON(drivers_json)=1", name="drivers_json"),
        CheckConstraint("data_cutoff_at <= created_at", name="cutoff_before_created"),
        CheckConstraint("eye IS NULL OR eye IN ('OD','OS')", name="eye_valid"),
        {"schema": "anomaly"},
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    astronaut_id: Mapped[str] = mapped_column(
        Unicode(32), ForeignKey("core.Astronauts.astronaut_id")
    )
    mission_day: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[dt.datetime] = mapped_column(
        DATETIME2(3), server_default=text("SYSUTCDATETIME()")
    )
    module_scope: Mapped[str] = mapped_column(String(24))
    measurement: Mapped[str | None] = mapped_column(
        String(60), ForeignKey("anomaly.MeasurementDefinitions.measurement_code")
    )
    eye: Mapped[str | None] = mapped_column(CHAR(2))
    algorithm: Mapped[str] = mapped_column(String(40))
    model_version: Mapped[str | None] = mapped_column(Unicode(100))
    anomaly_score: Mapped[float | None] = mapped_column(Float(precision=53))
    is_anomaly: Mapped[bool] = mapped_column(Boolean)
    level: Mapped[str] = mapped_column(String(40))
    summary: Mapped[str] = mapped_column(Unicode(4000))
    drivers_json: Mapped[str] = mapped_column(UnicodeText)
    baseline_status: Mapped[str] = mapped_column(String(40))
    data_quality_status: Mapped[str] = mapped_column(String(40))
    recommendation: Mapped[str] = mapped_column(Unicode(2000))
    data_cutoff_at: Mapped[dt.datetime] = mapped_column(DATETIME2(3))


class AnalysisJob(Base):
    """ops.AnalysisJobs — kalıcı analiz işi, dondurulmuş girdi ve teknik durum (A3).

    request_json: şemaya önerilen ek sütun (sözleşme §11.1). İşçinin işi sıradan
    aldığında neyi analiz edeceğini (module_scope / session_id) buradan okur.
    """

    __tablename__ = "AnalysisJobs"
    __table_args__ = (
        UniqueConstraint("astronaut_id", "idempotency_key"),
        CheckConstraint("module IN ('anomaly','sans')", name="module_valid"),
        CheckConstraint(
            "state IN ('QUEUED','SYNCING','ANALYZING','COMPLETED','FAILED')", name="state_valid"
        ),
        CheckConstraint("attempts >= 0 AND retry_cycle >= 0", name="counters_nonneg"),
        CheckConstraint("ISJSON(request_json)=1", name="request_json"),
        CheckConstraint(
            "input_snapshot_json IS NULL OR ISJSON(input_snapshot_json)=1", name="snapshot_json"
        ),
        CheckConstraint("outcome_json IS NULL OR ISJSON(outcome_json)=1", name="outcome_json"),
        CheckConstraint(
            "provider_metadata_json IS NULL OR ISJSON(provider_metadata_json)=1",
            name="provider_metadata_json",
        ),
        CheckConstraint(
            "evaluation_status IS NULL OR evaluation_status IN"
            " ('evaluated','insufficient_data','invalid_data')",
            name="evaluation_status_valid",
        ),
        CheckConstraint(
            "(state IN ('SYNCING','ANALYZING') AND lease_token IS NOT NULL AND lease_until IS NOT NULL)"
            " OR (state NOT IN ('SYNCING','ANALYZING') AND lease_token IS NULL AND lease_until IS NULL)",
            name="lease_by_state",
        ),
        CheckConstraint(
            "(module='anomaly' AND sans_analysis_id IS NULL)"
            " OR (module='sans' AND anomaly_result_id IS NULL)",
            name="result_by_module",
        ),
        # İşçinin "sıradaki iş" sorgusu için
        Index("IX_AnalysisJobs_state_next_attempt_at", "state", "next_attempt_at"),
        {"schema": "ops"},
    )

    job_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    idempotency_key: Mapped[uuid.UUID] = mapped_column(Uuid)
    request_hash: Mapped[str] = mapped_column(CHAR(64))
    module: Mapped[str] = mapped_column(String(24))
    state: Mapped[str] = mapped_column(String(40), server_default=text("'QUEUED'"))
    request_json: Mapped[str] = mapped_column(UnicodeText)
    input_snapshot_json: Mapped[str | None] = mapped_column(UnicodeText)
    input_hash: Mapped[str | None] = mapped_column(CHAR(64))
    provider_metadata_json: Mapped[str | None] = mapped_column(UnicodeText)
    lease_token: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    lease_until: Mapped[dt.datetime | None] = mapped_column(DATETIME2(3))
    attempts: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    retry_cycle: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    next_attempt_at: Mapped[dt.datetime] = mapped_column(
        DATETIME2(3), server_default=text("SYSUTCDATETIME()")
    )
    evaluation_status: Mapped[str | None] = mapped_column(String(40))
    outcome_json: Mapped[str | None] = mapped_column(UnicodeText)
    error_code: Mapped[str | None] = mapped_column(String(40))
    created_at: Mapped[dt.datetime] = mapped_column(
        DATETIME2(3), server_default=text("SYSUTCDATETIME()")
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DATETIME2(3), server_default=text("SYSUTCDATETIME()")
    )
    astronaut_id: Mapped[str] = mapped_column(
        Unicode(32), ForeignKey("core.Astronauts.astronaut_id")
    )
    anomaly_result_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("anomaly.anomaly_results.id")
    )
    sans_analysis_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("sans.analiz.analysis_id")
    )
