"""A4: behavioral şeması — günlük check-in, haftalık ölçekler, bilişsel testler (şema v5.0 §7).

- Puan yönleri (loneliness, crew) ve PVT speed formülü teyit edilmedi: alanlar saklanır,
  anlam üretilmez. Uygulanmayan metrik NULL kalır; eksik veri 0 yapılmaz.
- source kaynak değeriyle (manual/seed) saklanır; ortak DTO'da seed → synthetic (A5).
- created_at/updated_at şemada varsayılansızdır; servis DB saatini yazar. Check-in
  güncellemesinde updated_at, 412 (ETag) kontrolünün dayanağıdır.
"""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    Float,
    ForeignKey,
    Integer,
    Unicode,
    UnicodeText,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.mssql import DATETIME2, TIME
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

ASTRONAUT_FK = "core.Astronauts.astronaut_id"


class Checkin(Base):
    """Günlük check-in; aynı astronot + tarih tek satırdır, PUT ile güncellenir."""

    __tablename__ = "checkins"
    __table_args__ = (
        UniqueConstraint("astronaut_id", "date"),
        CheckConstraint("mood BETWEEN 0 AND 10", name="mood_range"),
        CheckConstraint("energy BETWEEN 0 AND 10", name="energy_range"),
        CheckConstraint("stress BETWEEN 0 AND 10", name="stress_range"),
        CheckConstraint("loneliness BETWEEN 0 AND 4", name="loneliness_range"),
        CheckConstraint("crew BETWEEN 0 AND 4", name="crew_range"),
        CheckConstraint("mood_index BETWEEN 0 AND 100", name="mood_index_range"),
        CheckConstraint("sleep_quality BETWEEN 1 AND 5", name="sleep_quality_range"),
        CheckConstraint("sleep_hours >= 0", name="sleep_hours_nonneg"),
        CheckConstraint("symptoms IS NULL OR ISJSON(symptoms)=1", name="symptoms_json"),
        CheckConstraint("source IN ('manual','seed')", name="source_valid"),
        {"schema": "behavioral"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[dt.date] = mapped_column(Date)
    mission_day: Mapped[int] = mapped_column(Integer)
    mood: Mapped[int] = mapped_column(Integer)
    energy: Mapped[int] = mapped_column(Integer)
    stress: Mapped[int] = mapped_column(Integer)
    loneliness: Mapped[int] = mapped_column(Integer)  # yön teyit edilecek
    crew: Mapped[int] = mapped_column(Integer)  # anlam/yön teyit edilecek
    mood_index: Mapped[float] = mapped_column(Float(precision=53))
    bed_time: Mapped[dt.time] = mapped_column(TIME(precision=0))
    wake_time: Mapped[dt.time] = mapped_column(TIME(precision=0))
    sleep_hours: Mapped[float] = mapped_column(Float(precision=53))
    sleep_quality: Mapped[int] = mapped_column(Integer)
    symptoms: Mapped[str | None] = mapped_column(UnicodeText)  # baş ağrısı hariç; o sans.semptom'da
    source: Mapped[str] = mapped_column(Unicode(200))
    created_at: Mapped[dt.datetime] = mapped_column(DATETIME2(3))
    updated_at: Mapped[dt.datetime] = mapped_column(DATETIME2(3))
    astronaut_id: Mapped[str] = mapped_column(Unicode(32), ForeignKey(ASTRONAUT_FK))


class WeeklyAssessment(Base):
    """WHO-5 / PHQ-2 / GAD-2. Alarm üretmez; genel model girdisine taşınmaz."""

    __tablename__ = "weekly_assessments"
    __table_args__ = (
        UniqueConstraint("astronaut_id", "client_request_id"),
        CheckConstraint("who5_score BETWEEN 0 AND 100", name="who5_range"),
        CheckConstraint("phq2_score BETWEEN 0 AND 6", name="phq2_range"),
        CheckConstraint("gad2_score BETWEEN 0 AND 6", name="gad2_range"),
        CheckConstraint("ISJSON(answers)=1", name="answers_json"),
        {"schema": "behavioral"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    taken_at: Mapped[dt.datetime] = mapped_column(DATETIME2(3))
    mission_day: Mapped[int] = mapped_column(Integer)
    answers: Mapped[str] = mapped_column(UnicodeText)
    who5_score: Mapped[int] = mapped_column(Integer)
    phq2_score: Mapped[int] = mapped_column(Integer)
    gad2_score: Mapped[int] = mapped_column(Integer)
    share_with_crew_medical: Mapped[bool] = mapped_column(Boolean, server_default=text("0"))
    source: Mapped[str] = mapped_column(Unicode(200))
    astronaut_id: Mapped[str] = mapped_column(Unicode(32), ForeignKey(ASTRONAUT_FK))
    client_request_id: Mapped[uuid.UUID] = mapped_column(Uuid)


class CognitiveTest(Base):
    """Tek PVT / rotation / DSST oturumu. Test türüne uygulanmayan metrik NULL olmak zorunda."""

    __tablename__ = "cognitive_tests"
    __table_args__ = (
        UniqueConstraint("astronaut_id", "client_request_id"),
        CheckConstraint("test_type IN ('pvt','rotation','dsst')", name="test_type_valid"),
        CheckConstraint("duration_s > 0 AND n_trials >= 0", name="duration_trials"),
        CheckConstraint("accuracy IS NULL OR accuracy BETWEEN 0 AND 1", name="accuracy_range"),
        CheckConstraint("ISJSON(raw)=1", name="raw_json"),
        CheckConstraint(
            "(valid=1 AND invalid_reason IS NULL) OR (valid=0 AND invalid_reason IS NOT NULL)",
            name="invalid_reason",
        ),
        CheckConstraint(
            "(test_type='pvt' AND accuracy IS NULL AND correct_count IS NULL)"
            " OR (test_type='rotation' AND median_rt_ms IS NULL AND speed IS NULL AND lapses IS NULL"
            " AND false_starts IS NULL AND correct_count IS NULL)"
            " OR (test_type='dsst' AND mean_rt_ms IS NULL AND median_rt_ms IS NULL AND speed IS NULL"
            " AND lapses IS NULL AND false_starts IS NULL)",
            name="metrics_by_type",
        ),
        {"schema": "behavioral"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    taken_at: Mapped[dt.datetime] = mapped_column(DATETIME2(3))
    mission_day: Mapped[int] = mapped_column(Integer)
    test_type: Mapped[str] = mapped_column(Unicode(200))
    duration_s: Mapped[int] = mapped_column(Integer)
    n_trials: Mapped[int] = mapped_column(Integer)
    mean_rt_ms: Mapped[float | None] = mapped_column(Float(precision=53))
    median_rt_ms: Mapped[float | None] = mapped_column(Float(precision=53))
    speed: Mapped[float | None] = mapped_column(Float(precision=53))  # formül teyit edilmedi
    lapses: Mapped[int | None] = mapped_column(Integer)
    false_starts: Mapped[int | None] = mapped_column(Integer)
    accuracy: Mapped[float | None] = mapped_column(Float(precision=53))
    correct_count: Mapped[int | None] = mapped_column(Integer)
    valid: Mapped[bool] = mapped_column(Boolean)
    invalid_reason: Mapped[str | None] = mapped_column(Unicode(500))
    device: Mapped[str] = mapped_column(Unicode(200))
    raw: Mapped[str] = mapped_column(UnicodeText)
    source: Mapped[str] = mapped_column(Unicode(200))
    astronaut_id: Mapped[str] = mapped_column(Unicode(32), ForeignKey(ASTRONAUT_FK))
    client_request_id: Mapped[uuid.UUID] = mapped_column(Uuid)
