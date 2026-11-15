"""Haftalık ölçek servisi (WHO-5, PHQ-2, GAD-2).

GİZLİLİK: bu modül log yazmaz. Madde cevapları ve puanlar hiçbir log / print çağrısına verilmez.
support_note saklanmaz, çıktıda hesaplanır.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from typing import Callable

from app.core.behavioral_settings import WEEKLY_INTERVAL_DAYS
from app.repositories.behavioral import WeeklyRecord, WeeklyRepository
from app.schemas.behavioral_module import Page, WeeklyIn, WeeklyOut
from app.services.behavioral_errors import BehavioralError
from app.services.behavioral_paging import (
    DEFAULT_LIMIT, check_limit, check_range, decode_position, encode_position,
)
from app.services.behavioral_scoring import score_gad2, score_phq2, score_who5

WEEKLY_INTERVAL = timedelta(days=WEEKLY_INTERVAL_DAYS)
SUPPORT_THRESHOLD = 3       # phq2_score >= 3 veya gad2_score >= 3 (questions.json support_rule)


def needs_support(phq2_score: int, gad2_score: int) -> bool:
    return phq2_score >= SUPPORT_THRESHOLD or gad2_score >= SUPPORT_THRESHOLD


def _to_out(record: WeeklyRecord) -> WeeklyOut:
    fields = {name: getattr(record, name) for name in WeeklyOut.model_fields if name != "support_note"}
    return WeeklyOut(**fields, support_note=needs_support(record.phq2_score, record.gad2_score))


class WeeklyService:
    def __init__(self, repo: WeeklyRepository, mission_start: date,
                 now: Callable[[], datetime]) -> None:
        self._repo = repo
        self._mission_start = mission_start
        self._now = now

    def mission_day(self, d: date) -> int:
        return (d - self._mission_start).days + 1

    def submit(self, astronaut_id: str, data: WeeklyIn) -> tuple[WeeklyOut, bool]:
        # 1. Tekrar gönderim, 7 gün kontrolünden önce
        existing = self._repo.get_by_client_request_id(astronaut_id, data.client_request_id)
        if existing is not None:
            return _to_out(existing), False

        now = self._now().astimezone(timezone.utc)
        today = now.date()
        if today < self._mission_start:
            raise BehavioralError("validation_error", "Mission has not started yet", ["date"])

        # 2. Son kayıttan bu yana 7 gün geçmeli
        latest = self._repo.get_latest(astronaut_id)
        if latest is not None and (today - latest.date) < WEEKLY_INTERVAL:
            due = latest.date + WEEKLY_INTERVAL
            raise BehavioralError("weekly_not_due",
                                  f"Next weekly assessment is due on {due.isoformat()}")

        # 3. Puanla ve kaydet
        answers = data.answers.model_dump()
        record = self._repo.add(WeeklyRecord(
            id=None, astronaut_id=astronaut_id, client_request_id=data.client_request_id,
            date=today, mission_day=self.mission_day(today), answers=answers,
            who5_score=score_who5(answers), phq2_score=score_phq2(answers),
            gad2_score=score_gad2(answers),
            share_with_crew_medical=data.share_with_crew_medical,
            source="manual", created_at=now,
        ))
        return _to_out(record), True

    def list(self, astronaut_id: str, date_from: date | None, date_to: date | None,
             limit: int = DEFAULT_LIMIT, cursor: str | None = None) -> Page[WeeklyOut]:
        check_limit(limit)
        check_range(date_from, date_to)
        after = decode_position(cursor) if cursor is not None else None
        records = self._repo.list(astronaut_id, date_from, date_to, limit + 1, after)
        page, has_more = records[:limit], len(records) > limit
        return Page[WeeklyOut](
            items=[_to_out(r) for r in page],
            next_cursor=encode_position(page[-1].created_at, page[-1].id) if has_more else None,
        )

    def set_sharing(self, astronaut_id: str, id: int, share: bool) -> WeeklyOut:
        if not isinstance(share, bool):
            raise BehavioralError("validation_error", "share must be a boolean",
                                  ["share_with_crew_medical"])
        record = self._repo.get_by_id(astronaut_id, id)
        if record is None:
            raise BehavioralError("not_found", "Weekly assessment not found")
        return _to_out(self._repo.update(replace(record, share_with_crew_medical=share)))
