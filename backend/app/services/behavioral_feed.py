"""Daily behavioral metrics for the anomaly module.

This is an in-process Python API, NOT an HTTP endpoint: the anomaly module runs in the
same backend and calls `DailyMetricsFeed.daily_metrics(astronaut_id, date_from, date_to)`.

It returns one row per calendar day in the range (days without data included), oldest
first. Metric names are a contract shared with the anomaly module and the knowledge cards;
do not rename them.

Privacy: weekly assessment data (WHO-5 / PHQ-2 / GAD-2 scores, item answers, sharing
flag) is never part of this feed. The feed does not even receive the weekly repository.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Callable

from pydantic import BaseModel

from app.core.behavioral_settings import CHECKIN_MISSING_DAYS
from app.repositories.behavioral import CheckinRepository, CognitiveTestRecord, CognitiveTestRepository
from app.services.behavioral_calendar import consecutive_missing, mission_day
from app.services.behavioral_errors import BehavioralError

_MANY = 10_000


class DailyMetrics(BaseModel):
    date: date
    mission_day: int
    checkin_done: bool
    mood_index: float | None
    stress: int | None
    loneliness: int | None
    crew_relation: int | None
    sleep_hours: float | None
    sleep_quality: int | None
    symptoms: list[str]
    pvt_mean_rt_ms: float | None
    pvt_lapses: int | None
    pvt_false_starts: int | None
    rotation_accuracy: float | None
    rotation_mean_rt_ms: float | None
    checkin_missing: bool


def _latest_valid(tests: list[CognitiveTestRecord]) -> dict[tuple[date, str], CognitiveTestRecord]:
    """(gün, test türü) başına en son (started_at, id) geçerli test."""
    latest: dict[tuple[date, str], CognitiveTestRecord] = {}
    for t in tests:
        if not t.valid:
            continue
        key = (t.date, t.test_type)
        if key not in latest or (t.started_at, t.id) > (latest[key].started_at, latest[key].id):
            latest[key] = t
    return latest


class DailyMetricsFeed:
    def __init__(self, checkin_repo: CheckinRepository, test_repo: CognitiveTestRepository,
                 mission_start: date, now: Callable[[], datetime]) -> None:
        self._checkins = checkin_repo
        self._tests = test_repo
        self._mission_start = mission_start
        self._now = now

    def daily_metrics(self, astronaut_id: str, date_from: date, date_to: date) -> list[DailyMetrics]:
        today = self._now().astimezone(timezone.utc).date()
        if date_from > date_to:
            raise BehavioralError("validation_error", "date_from must not be later than date_to",
                                  ["date_from", "date_to"])
        if date_from < self._mission_start:
            raise BehavioralError("validation_error", "date_from is before mission start", ["date_from"])
        if date_to > today:
            raise BehavioralError("future_date", "date_to cannot be in the future", ["date_to"])

        # Ardışık eksik sayımı aralığın öncesine de bakar -> görev başından itibaren oku
        checkins = {r.date: r for r in self._checkins.list(
            astronaut_id, self._mission_start, date_to, _MANY, None)}
        tests = _latest_valid(self._tests.list(astronaut_id, date_from, date_to, None, _MANY, None))

        rows = []
        d = date_from
        while d <= date_to:
            c = checkins.get(d)
            pvt, rot = tests.get((d, "pvt")), tests.get((d, "rotation"))
            last_counted = d - timedelta(days=1) if d == today else d     # bugün henüz bitmedi
            rows.append(DailyMetrics(
                date=d, mission_day=mission_day(d, self._mission_start), checkin_done=c is not None,
                mood_index=c.mood_index if c else None, stress=c.stress if c else None,
                loneliness=c.loneliness if c else None, crew_relation=c.crew_relation if c else None,
                sleep_hours=c.sleep_hours if c else None, sleep_quality=c.sleep_quality if c else None,
                symptoms=list(c.symptoms) if c else [],
                pvt_mean_rt_ms=pvt.mean_rt_ms if pvt else None,
                pvt_lapses=pvt.lapses if pvt else None,
                pvt_false_starts=pvt.false_starts if pvt else None,
                rotation_accuracy=rot.accuracy if rot else None,
                rotation_mean_rt_ms=rot.mean_rt_ms if rot else None,
                checkin_missing=consecutive_missing(checkins, last_counted, self._mission_start)
                >= CHECKIN_MISSING_DAYS,
            ))
            d += timedelta(days=1)
        return rows
