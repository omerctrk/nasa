"""Davranışsal modül: istek / cevap şemaları (Pydantic v2).

Bu dosya yalnız DOĞRULAR; puan hesaplama app.services.behavioral_scoring içindedir.
Giriş modellerinde bilinmeyen alan hatadır (extra="forbid").
"""
import datetime as dt
from typing import Annotated, Generic, Literal, TypeVar, Union
from uuid import UUID

from pydantic import (
    UUID4, AfterValidator, AwareDatetime, BaseModel, ConfigDict, Field,
    StrictBool, StrictInt, StringConstraints, field_validator, model_validator,
)

from app.services.behavioral_scoring import SYMPTOM_CODES

ROTATION_ANGLES = (0, 60, 120, 180)
PVT_MAX_TRIALS = 200
ROTATION_MAX_TRIALS = 16


def _check_angle(value: int) -> int:
    if value not in ROTATION_ANGLES:
        raise ValueError(f"angle must be one of {list(ROTATION_ANGLES)}")
    return value


Score0to10 = Annotated[StrictInt, Field(ge=0, le=10)]
Score0to4 = Annotated[StrictInt, Field(ge=0, le=4)]
Score0to5 = Annotated[StrictInt, Field(ge=0, le=5)]
Score0to3 = Annotated[StrictInt, Field(ge=0, le=3)]
Score1to5 = Annotated[StrictInt, Field(ge=1, le=5)]
TrialIndex = Annotated[StrictInt, Field(ge=0)]
ClockTime = Annotated[str, StringConstraints(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")]
RotationAngle = Annotated[StrictInt, AfterValidator(_check_angle)]


class _InModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _unique_trial_indexes(trials: list) -> list:
    seen = set()
    for t in trials:
        if t.i in seen:
            raise ValueError(f"duplicate trial index: {t.i}")
        seen.add(t.i)
    return trials


# ---------------------------------------------------------------- giriş: check-in

class CheckinIn(_InModel):
    mood: Score0to10
    energy: Score0to10
    stress: Score0to10
    loneliness: Score0to4
    crew_relation: Score0to4
    bed_time: ClockTime
    wake_time: ClockTime
    sleep_quality: Score1to5
    symptoms: list[str] = Field(default_factory=list)

    @field_validator("symptoms")
    @classmethod
    def _known_unique_symptoms(cls, value: list[str]) -> list[str]:
        unknown = [s for s in value if s not in SYMPTOM_CODES]
        if unknown:
            raise ValueError(f"unknown symptom code(s): {unknown}")
        if len(set(value)) != len(value):
            raise ValueError("duplicate symptom code")
        return value


# ---------------------------------------------------------------- giriş: bilişsel testler

class PvtTrial(_InModel):
    i: TrialIndex
    delay_ms: float = Field(ge=1000, le=4000)
    rt_ms: float | None = Field(ge=0)          # zorunlu; cevapsız deneme için açıkça null
    false_start: StrictBool

    @model_validator(mode="after")
    def _false_start_has_no_rt(self):
        if self.false_start and self.rt_ms is not None:
            raise ValueError("rt_ms must be null when false_start is true")
        return self


class RotationTrial(_InModel):
    i: TrialIndex
    shape: Literal["s1", "s2", "s3", "s4"]
    angle: RotationAngle
    mirror: StrictBool
    answer: Literal["same", "mirror"] | None   # zorunlu; cevapsız deneme için açıkça null
    rt_ms: float | None = Field(ge=0, le=7000)

    @model_validator(mode="after")
    def _answer_and_rt_together(self):
        if self.answer is None and self.rt_ms is not None:
            raise ValueError("rt_ms must be null when answer is null")
        if self.answer is not None and self.rt_ms is None:
            raise ValueError("rt_ms is required when answer is given")
        return self


class _TestInBase(_InModel):
    client_request_id: UUID4
    started_at: AwareDatetime
    finished_at: AwareDatetime
    device: str | None = Field(default=None, max_length=64)

    @model_validator(mode="after")
    def _finished_not_before_started(self):
        if self.finished_at < self.started_at:
            raise ValueError("finished_at must not be earlier than started_at")
        return self


class PvtTestIn(_TestInBase):
    test_type: Literal["pvt"]
    trials: list[PvtTrial] = Field(max_length=PVT_MAX_TRIALS)

    _unique_i = field_validator("trials")(_unique_trial_indexes)


class RotationTestIn(_TestInBase):
    test_type: Literal["rotation"]
    trials: list[RotationTrial] = Field(max_length=ROTATION_MAX_TRIALS)

    _unique_i = field_validator("trials")(_unique_trial_indexes)


CognitiveTestIn = Annotated[Union[PvtTestIn, RotationTestIn], Field(discriminator="test_type")]


# ---------------------------------------------------------------- giriş: haftalık ölçekler

class WeeklyAnswers(_InModel):
    who5_1: Score0to5
    who5_2: Score0to5
    who5_3: Score0to5
    who5_4: Score0to5
    who5_5: Score0to5
    phq2_1: Score0to3
    phq2_2: Score0to3
    gad2_1: Score0to3
    gad2_2: Score0to3


class WeeklyIn(_InModel):
    client_request_id: UUID4
    answers: WeeklyAnswers
    share_with_crew_medical: StrictBool = False



class SharingIn(_InModel):
    """PUT /weekly-assessments/{id}/sharing gövdesi."""
    share_with_crew_medical: StrictBool


# ---------------------------------------------------------------- çıkış

class CheckinOut(BaseModel):
    id: int
    date: dt.date
    mission_day: int
    mood: int
    energy: int
    stress: int
    loneliness: int
    crew_relation: int
    bed_time: str
    wake_time: str
    sleep_quality: int
    symptoms: list[str]
    mood_index: float
    sleep_hours: float
    source: str
    created_at: dt.datetime
    updated_at: dt.datetime


class CognitiveTestOut(BaseModel):
    id: int
    client_request_id: UUID
    test_type: Literal["pvt", "rotation"]
    date: dt.date
    mission_day: int
    started_at: dt.datetime
    finished_at: dt.datetime
    device: str | None
    n_trials: int
    mean_rt_ms: float | None
    median_rt_ms: float | None      # yalnız PVT
    speed: float | None             # yalnız PVT
    lapses: int | None              # yalnız PVT
    false_starts: int | None        # yalnız PVT
    accuracy: float | None          # yalnız döndürme
    valid: bool
    invalid_reason: str | None
    source: str


class CognitiveTestDetail(CognitiveTestOut):
    trials: list[PvtTrial] | list[RotationTrial]


class WeeklyOut(BaseModel):
    id: int
    client_request_id: UUID
    date: dt.date
    mission_day: int
    who5_score: int
    phq2_score: int
    gad2_score: int
    support_note: bool
    share_with_crew_medical: bool
    created_at: dt.datetime



class TodayCheckin(BaseModel):
    done: bool
    etag: str | None


class TodaySignals(BaseModel):
    """Eksik veri sinyalleri. Sayım dünden geriye yapılır (bugün henüz bitmedi)."""
    checkin_missing: bool
    consecutive_missed_checkin_days: int
    missed_checkin_days_7d: int
    last_checkin_date: dt.date | None
    tests_missing: bool
    last_test_date: dt.date | None


class TodayOut(BaseModel):
    """Bugünün görev durumu. Haftalık puan içermez."""
    date: dt.date
    mission_day: int
    checkin: TodayCheckin
    tests_due: list[Literal["pvt", "rotation"]]
    tests_done: list[Literal["pvt", "rotation"]]
    weekly_due: bool
    weekly_last_date: dt.date | None
    weekly_next_date: dt.date | None
    signals: TodaySignals


T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    next_cursor: str | None = None


class ErrorDetail(BaseModel):
    code: str
    message: str
    fields: list[str] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    detail: ErrorDetail
