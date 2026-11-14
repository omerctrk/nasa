"""A2: anomaly.MeasurementDefinitions ve anomaly.MeasurementRecords (şema v5.0 §7).

MeasurementRecords yalnız FİZYOLOJİK manuel/demo ölçümlerin asıl kaydıdır; göz ve
davranış verisinin kopyası tutulmaz (onlar anomaly.v_measurements VIEW'ından okunur, A5).
"""
from __future__ import annotations

import datetime as dt
import uuid
from decimal import Decimal

from sqlalchemy import (
    CHAR,
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    Numeric,
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


class MeasurementDefinition(Base):
    """Ölçüm kodu sözlüğü: modül, kanonik birim, değer türü, protokol, kötüleşme yönü."""

    __tablename__ = "MeasurementDefinitions"
    __table_args__ = (
        UniqueConstraint("module", "measurement_code"),
        CheckConstraint("module IN ('physiological','behavioral','sans')", name="module_valid"),
        CheckConstraint("value_kind IN ('numeric','integer','category')", name="value_kind_valid"),
        {"schema": "anomaly"},
    )

    measurement_code: Mapped[str] = mapped_column(String(60), primary_key=True)
    module: Mapped[str] = mapped_column(String(24))
    canonical_unit: Mapped[str] = mapped_column(Unicode(32))
    value_kind: Mapped[str] = mapped_column(String(40))
    protocol_version: Mapped[str] = mapped_column(String(40))
    # higher/lower/context_dependent/unconfirmed — teyitsiz yön varsayılmaz
    worsening_direction: Mapped[str] = mapped_column(String(40))


class MeasurementRecord(Base):
    """Fizyolojik ölçüm. Aynı (astronaut_id, client_request_id) ikinci kez yazılamaz."""

    __tablename__ = "MeasurementRecords"
    __table_args__ = (
        UniqueConstraint("astronaut_id", "client_request_id"),
        CheckConstraint("eye_code IN ('OD','OS','NA')", name="eye_code_valid"),
        CheckConstraint("eye_code='NA'", name="eye_code_na"),  # fizyolojik: göz yok
        CheckConstraint("value_num IS NULL OR value_text IS NULL", name="single_value"),
        CheckConstraint(
            "valid=0 OR value_num IS NOT NULL OR value_text IS NOT NULL", name="valid_has_value"
        ),
        CheckConstraint(
            "quality_score IS NULL OR quality_score BETWEEN 0 AND 1", name="quality_score_range"
        ),
        CheckConstraint("metadata_json IS NULL OR ISJSON(metadata_json)=1", name="metadata_json"),
        CheckConstraint("source IN ('manual','synthetic')", name="source_valid"),
        CheckConstraint(
            "(time_precision='date' AND measured_at IS NULL) OR (time_precision='timestamp'"
            " AND measured_at IS NOT NULL AND measured_date=CONVERT(date,measured_at))",
            name="time_precision",
        ),
        {"schema": "anomaly"},
    )

    record_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    measurement_code: Mapped[str] = mapped_column(
        String(60), ForeignKey("anomaly.MeasurementDefinitions.measurement_code")
    )
    eye_code: Mapped[str] = mapped_column(CHAR(2))
    value_num: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    value_text: Mapped[str | None] = mapped_column(Unicode(256))
    valid: Mapped[bool] = mapped_column(Boolean)
    quality_score: Mapped[Decimal | None] = mapped_column(Numeric(7, 6))
    metadata_json: Mapped[str | None] = mapped_column(UnicodeText)
    astronaut_id: Mapped[str] = mapped_column(
        Unicode(32), ForeignKey("core.Astronauts.astronaut_id")
    )
    client_request_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    measured_date: Mapped[dt.date] = mapped_column(Date)
    measured_at: Mapped[dt.datetime | None] = mapped_column(DATETIME2(3))
    time_precision: Mapped[str] = mapped_column(String(9))
    mission_day: Mapped[int | None] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[dt.datetime] = mapped_column(
        DATETIME2(3), server_default=text("SYSUTCDATETIME()")
    )
