"""Bilişsel test servisi (PVT ve zihinsel döndürme).

Puanlama behavioral_scoring'de; geçersiz oturum da kaydedilir (valid False + invalid_reason).
Saat ve görev başlangıcı dışarıdan verilir.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Callable

from app.repositories.behavioral import CognitiveTestRecord, CognitiveTestRepository
from app.schemas.behavioral_module import (
    CognitiveTestDetail, CognitiveTestOut, Page, PvtTestIn, RotationTestIn,
)
from app.services.behavioral_errors import BehavioralError
from app.services.behavioral_paging import (
    DEFAULT_LIMIT, check_limit, check_range, decode_position, encode_position,
)
from app.services.behavioral_scoring import score_pvt, score_rotation

TEST_TYPES = ("pvt", "rotation")
CLOCK_TOLERANCE = timedelta(minutes=5)      # cihaz saati sunucudan biraz ileride olabilir
SCORERS = {"pvt": score_pvt, "rotation": score_rotation}
METRIC_FIELDS = ("n_trials", "mean_rt_ms", "median_rt_ms", "speed", "lapses",
                 "false_starts", "accuracy", "valid", "invalid_reason")


def _to_out(record: CognitiveTestRecord) -> CognitiveTestOut:
    return CognitiveTestOut(**{name: getattr(record, name) for name in CognitiveTestOut.model_fields})


def _to_detail(record: CognitiveTestRecord) -> CognitiveTestDetail:
    return CognitiveTestDetail(**{name: getattr(record, name) for name in CognitiveTestDetail.model_fields})


class CognitiveTestService:
    def __init__(self, repo: CognitiveTestRepository, mission_start: date,
                 now: Callable[[], datetime]) -> None:
        self._repo = repo
        self._mission_start = mission_start
        self._now = now

    def mission_day(self, d: date) -> int:
        return (d - self._mission_start).days + 1

    def submit(self, astronaut_id: str,
               data: PvtTestIn | RotationTestIn) -> tuple[CognitiveTestOut, bool]:
        existing = self._repo.get_by_client_request_id(astronaut_id, data.client_request_id)
        if existing is not None:
            return _to_out(existing), False

        now = self._now().astimezone(timezone.utc)
        if data.started_at > now + CLOCK_TOLERANCE:
            raise BehavioralError("future_date", "started_at cannot be in the future", ["started_at"])
        started_utc = data.started_at.astimezone(timezone.utc)
        d = started_utc.date()
        if d < self._mission_start:
            raise BehavioralError("validation_error", "Test date is before mission start", ["started_at"])

        trials = [t.model_dump() for t in data.trials]
        metrics = SCORERS[data.test_type](trials)
        record = self._repo.add(CognitiveTestRecord(
            id=None, astronaut_id=astronaut_id, client_request_id=data.client_request_id,
            test_type=data.test_type, date=d, mission_day=self.mission_day(d),
            started_at=started_utc, finished_at=data.finished_at.astimezone(timezone.utc),
            device=data.device, trials=trials,
            **{name: metrics[name] for name in METRIC_FIELDS},   # correct_count API'de yok
            source="manual", created_at=now,
        ))
        return _to_out(record), True

    def get(self, astronaut_id: str, id: int) -> CognitiveTestDetail:
        record = self._repo.get_by_id(astronaut_id, id)
        if record is None:
            raise BehavioralError("not_found", "Cognitive test not found")
        return _to_detail(record)

    def list(self, astronaut_id: str, date_from: date | None, date_to: date | None,
             test_type: str | None = None, limit: int = DEFAULT_LIMIT,
             cursor: str | None = None) -> Page[CognitiveTestOut]:
        check_limit(limit)
        check_range(date_from, date_to)
        if test_type is not None and test_type not in TEST_TYPES:
            raise BehavioralError("validation_error", f"test_type must be one of {list(TEST_TYPES)}",
                                  ["test_type"])
        after = decode_position(cursor) if cursor is not None else None
        records = self._repo.list(astronaut_id, date_from, date_to, test_type, limit + 1, after)
        page, has_more = records[:limit], len(records) > limit
        return Page[CognitiveTestOut](
            items=[_to_out(r) for r in page],
            next_cursor=encode_position(page[-1].started_at, page[-1].id) if has_more else None,
        )
