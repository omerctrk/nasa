"""Check-in servisi: iş kuralları (tarih, ön koşul başlıkları, ETag, tekrar gönderim).

Saklama repository'de, hesap behavioral_scoring'de; saat ve görev başlangıcı dışarıdan verilir.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, time, timezone
from typing import Callable

from app.repositories.behavioral import CheckinRecord, CheckinRepository
from app.schemas.behavioral_module import CheckinIn, CheckinOut, Page
from app.services.behavioral_errors import BehavioralError
from app.services.behavioral_paging import (
    DEFAULT_LIMIT, check_limit, check_range, decode_date, encode_date,
)
from app.services.behavioral_scoring import mood_index, sleep_hours

INPUT_FIELDS = ("mood", "energy", "stress", "loneliness", "crew_relation",
                "bed_time", "wake_time", "sleep_quality", "symptoms")


def etag(record: CheckinRecord) -> str:
    return f'"c-{record.id}-{record.version}"'


def _to_out(record: CheckinRecord) -> CheckinOut:
    return CheckinOut(**{name: getattr(record, name) for name in CheckinOut.model_fields})


def _clock(value: str) -> time:
    return time.fromisoformat(value)


class CheckinService:
    def __init__(self, repo: CheckinRepository, mission_start: date,
                 now: Callable[[], datetime]) -> None:
        self._repo = repo
        self._mission_start = mission_start
        self._now = now

    def mission_day(self, d: date) -> int:
        return (d - self._mission_start).days + 1

    # ------------------------------------------------------------ okuma

    def get(self, astronaut_id: str, d: date) -> tuple[CheckinOut, str]:
        record = self._repo.get_by_date(astronaut_id, d)
        if record is None:
            raise BehavioralError("checkin_not_found", f"No check-in for {d.isoformat()}")
        return _to_out(record), etag(record)

    def list(self, astronaut_id: str, date_from: date | None, date_to: date | None,
             limit: int = DEFAULT_LIMIT, cursor: str | None = None) -> Page[CheckinOut]:
        check_limit(limit)
        check_range(date_from, date_to)
        after_date = decode_date(cursor) if cursor is not None else None
        records = self._repo.list(astronaut_id, date_from, date_to, limit + 1, after_date)
        page, has_more = records[:limit], len(records) > limit
        return Page[CheckinOut](
            items=[_to_out(r) for r in page],
            next_cursor=encode_date(page[-1].date) if has_more else None,
        )

    # ------------------------------------------------------------ yazma

    def put(self, astronaut_id: str, d: date, data: CheckinIn,
            if_match: str | None, if_none_match: str | None) -> tuple[CheckinOut, str, bool]:
        now = self._now().astimezone(timezone.utc)
        if d > now.date():
            raise BehavioralError("future_date", "Check-in date cannot be in the future", ["date"])
        if d < self._mission_start:
            raise BehavioralError("validation_error", "Check-in date is before mission start", ["date"])
        if (if_match is None) == (if_none_match is None):
            raise BehavioralError("precondition_required",
                                  "Exactly one of If-Match or If-None-Match is required")

        existing = self._repo.get_by_date(astronaut_id, d)
        values = data.model_dump()
        inputs = {name: values[name] for name in INPUT_FIELDS}

        # Tekrar gönderim: aynı gövde -> başlıklara bakmadan mevcut kayıt
        if existing is not None and all(getattr(existing, k) == v for k, v in inputs.items()):
            return _to_out(existing), etag(existing), False

        computed = {
            "mood_index": mood_index(data.mood, data.energy, data.stress),
            "sleep_hours": sleep_hours(_clock(data.bed_time), _clock(data.wake_time)),
        }

        if if_none_match is not None:
            if if_none_match != "*":
                raise BehavioralError("validation_error", 'If-None-Match only supports "*"')
            if existing is not None:
                raise BehavioralError("etag_mismatch", "A check-in already exists for this date")
            record = self._repo.add(CheckinRecord(
                id=None, astronaut_id=astronaut_id, date=d, mission_day=self.mission_day(d),
                **inputs, **computed, source="manual", version=1, created_at=now, updated_at=now,
            ))
            return _to_out(record), etag(record), True

        if existing is None:
            raise BehavioralError("etag_mismatch", "No check-in exists for this date")
        if if_match != "*" and if_match != etag(existing):
            raise BehavioralError("etag_mismatch", "Check-in was modified; reload and retry")
        record = self._repo.update(replace(
            existing, **inputs, **computed, version=existing.version + 1, updated_at=now,
        ))
        return _to_out(record), etag(record), False
