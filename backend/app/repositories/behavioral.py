"""Davranışsal modül repository arayüzü.

Repository yalnız saklar ve okur: iş kuralı içermez, commit yapmaz.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol
from uuid import UUID


@dataclass
class CheckinRecord:
    id: int | None                  # add() atar
    astronaut_id: str
    date: date
    mission_day: int
    mood: int
    energy: int
    stress: int
    loneliness: int
    crew_relation: int
    bed_time: str                   # "HH:MM"
    wake_time: str                  # "HH:MM"
    sleep_quality: int
    symptoms: list[str]
    mood_index: float
    sleep_hours: float
    source: str
    version: int
    created_at: datetime
    updated_at: datetime


class CheckinRepository(Protocol):
    def get_by_date(self, astronaut_id: str, date: date) -> CheckinRecord | None: ...

    def list(self, astronaut_id: str, date_from: date | None, date_to: date | None,
             limit: int, after_date: date | None) -> list[CheckinRecord]:
        """date_from / date_to dahil; yeniden eskiye. after_date verilirse yalnız ondan eski kayıtlar."""
        ...

    def add(self, record: CheckinRecord) -> CheckinRecord:
        """Kaydı saklar ve id atar."""
        ...

    def update(self, record: CheckinRecord) -> CheckinRecord: ...


# ---------------------------------------------------------------- bilişsel testler

@dataclass
class CognitiveTestRecord:
    id: int | None                  # add() atar
    astronaut_id: str
    client_request_id: UUID
    test_type: str                  # "pvt" | "rotation"
    date: date                      # started_at'in UTC günü
    mission_day: int
    started_at: datetime
    finished_at: datetime
    device: str | None
    trials: list[dict]
    n_trials: int
    mean_rt_ms: float | None
    median_rt_ms: float | None
    speed: float | None
    lapses: int | None
    false_starts: int | None
    accuracy: float | None
    valid: bool
    invalid_reason: str | None
    source: str
    created_at: datetime


class CognitiveTestRepository(Protocol):
    def get_by_id(self, astronaut_id: str, id: int) -> CognitiveTestRecord | None: ...

    def get_by_client_request_id(self, astronaut_id: str,
                                 client_request_id: UUID) -> CognitiveTestRecord | None: ...

    def list(self, astronaut_id: str, date_from: date | None, date_to: date | None,
             test_type: str | None, limit: int,
             after: tuple[datetime, int] | None) -> list[CognitiveTestRecord]:
        """(started_at, id) sırasıyla yeniden eskiye. after verilirse yalnız ondan eski kayıtlar."""
        ...

    def add(self, record: CognitiveTestRecord) -> CognitiveTestRecord: ...


# ---------------------------------------------------------------- haftalık ölçekler

@dataclass
class WeeklyRecord:
    id: int | None                  # add() atar
    astronaut_id: str
    client_request_id: UUID
    date: date
    mission_day: int
    answers: dict[str, int]
    who5_score: int
    phq2_score: int
    gad2_score: int
    share_with_crew_medical: bool
    source: str
    created_at: datetime


class WeeklyRepository(Protocol):
    def get_by_id(self, astronaut_id: str, id: int) -> WeeklyRecord | None: ...

    def get_by_client_request_id(self, astronaut_id: str,
                                 client_request_id: UUID) -> WeeklyRecord | None: ...

    def get_latest(self, astronaut_id: str) -> WeeklyRecord | None:
        """En yeni kayıt ((date, created_at, id) sırasıyla)."""
        ...

    def list(self, astronaut_id: str, date_from: date | None, date_to: date | None,
             limit: int, after: tuple[datetime, int] | None) -> list[WeeklyRecord]:
        """(created_at, id) sırasıyla yeniden eskiye. after verilirse yalnız ondan eski kayıtlar."""
        ...

    def add(self, record: WeeklyRecord) -> WeeklyRecord: ...

    def update(self, record: WeeklyRecord) -> WeeklyRecord: ...
