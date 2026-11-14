"""anomaly.anomaly_results (A2) — ops.AnalysisJobs A3'te bu dosyaya eklenecek.

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
    Integer,
    String,
    Unicode,
    UnicodeText,
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
