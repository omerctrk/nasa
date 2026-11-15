"""Davranış veri girişi DTO'ları (A7, sahip: Aybala).

astronaut_id istemciden ALINMAZ (sözleşme §5): giriş yapan astronottan atanır.
mission_day istemciden alınmaz; görev başlangıcına göre backend hesaplar.
"""
from __future__ import annotations

import datetime as dt
import uuid
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from app.schemas.common import ContractModel

def utc(v: dt.datetime) -> dt.datetime:
    if v.tzinfo is None or v.utcoffset() is None:
        raise ValueError("zaman saat dilimi içermeli (UTC, 'Z')")
    return v.astimezone(dt.UTC)


def sleep_hours_between(bed: dt.time, wake: dt.time) -> float:
    """Yatış → uyanış süresi (saat); gece yarısını geçen uyku desteklenir."""
    b = bed.hour * 60 + bed.minute
    w = wake.hour * 60 + wake.minute
    return round(((w - b) % (24 * 60)) / 60, 2)


# --- Check-in -----------------------------------------------------------------------


class CheckinIn(ContractModel):
    """PUT /me/checkins/{date}. Aynı kişi+gün tek kayıttır; güncelleme If-Match ister."""

    mood: int = Field(ge=0, le=10)
    energy: int = Field(ge=0, le=10)
    stress: int = Field(ge=0, le=10)
    loneliness: int = Field(ge=0, le=4)  # yön teyit edilecek
    crew: int = Field(ge=0, le=4)  # anlam/yön teyit edilecek
    # AÇIK KARAR: mood_index formülü teyit edilmedi; backend uydurmaz. Formül gelene kadar
    # istemci gönderir, gelince bu alan kaldırılıp backend hesaplar.
    mood_index: float = Field(ge=0, le=100)
    bed_time: dt.time
    wake_time: dt.time
    sleep_quality: int = Field(ge=1, le=5)
    symptoms: list[str] | None = None  # belirti kodları (JSON listesi)


class CheckinOut(ContractModel):
    date: dt.date
    mission_day: int
    mood: int
    energy: int
    stress: int
    loneliness: int
    crew: int
    mood_index: float
    bed_time: dt.time
    wake_time: dt.time
    sleep_hours: float
    sleep_quality: int
    symptoms: list[str] | None
    source: str
    created_at: dt.datetime
    updated_at: dt.datetime


# --- Haftalık ölçek -----------------------------------------------------------------


class WeeklyIn(ContractModel):
    client_request_id: uuid.UUID
    taken_at: dt.datetime
    answers: dict[str, Any]  # WHO-5/PHQ-2/GAD-2 ham yanıtları (JSON nesnesi)
    who5_score: int = Field(ge=0, le=100)  # ham toplam × 4
    phq2_score: int = Field(ge=0, le=6)
    gad2_score: int = Field(ge=0, le=6)
    share_with_crew_medical: bool = False

    _utc = field_validator("taken_at")(utc)


class WeeklyOut(ContractModel):
    id: int
    taken_at: dt.datetime
    mission_day: int
    who5_score: int
    phq2_score: int
    gad2_score: int
    share_with_crew_medical: bool


# --- Bilişsel test ------------------------------------------------------------------

METRICS = ("mean_rt_ms", "median_rt_ms", "speed", "lapses", "false_starts", "accuracy",
           "correct_count")
ALLOWED = {
    "pvt": {"mean_rt_ms", "median_rt_ms", "speed", "lapses", "false_starts"},
    "rotation": {"mean_rt_ms", "accuracy"},
    "dsst": {"accuracy", "correct_count"},
}


class CognitiveIn(ContractModel):
    client_request_id: uuid.UUID
    taken_at: dt.datetime
    test_type: Literal["pvt", "rotation", "dsst"]
    duration_s: int = Field(gt=0)
    n_trials: int = Field(ge=0)
    mean_rt_ms: float | None = Field(default=None, ge=0)
    median_rt_ms: float | None = Field(default=None, ge=0)
    speed: float | None = None  # formül teyitsiz; saklanır, analize girmez
    lapses: int | None = Field(default=None, ge=0)
    false_starts: int | None = Field(default=None, ge=0)
    accuracy: float | None = Field(default=None, ge=0, le=1)
    correct_count: int | None = Field(default=None, ge=0)
    valid: bool = True
    invalid_reason: str | None = Field(default=None, max_length=500)
    device: str = Field(min_length=1, max_length=200)
    raw: list[Any] | dict[str, Any]

    _utc = field_validator("taken_at")(utc)

    @model_validator(mode="after")
    def _rules(self) -> CognitiveIn:
        extra = [m for m in METRICS if getattr(self, m) is not None
                 and m not in ALLOWED[self.test_type]]
        if extra:
            raise ValueError(f"{self.test_type} testinde bu metrikler olamaz: {', '.join(extra)}")
        if self.valid and self.invalid_reason is not None:
            raise ValueError("geçerli testte invalid_reason boş olmalı")
        if not self.valid and not (self.invalid_reason or "").strip():
            raise ValueError("geçersiz testte invalid_reason zorunlu")
        return self


class CognitiveOut(ContractModel):
    id: int
    taken_at: dt.datetime
    mission_day: int
    test_type: str
    valid: bool
