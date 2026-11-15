"""Bugün ekranı: check-in, test ve haftalık ölçek durumu + eksik veri sinyalleri.

Haftalık PUAN içermez; yalnız tarih bilgisi (son / sonraki) döner.
Eksik gün sayımı dünden geriye yapılır (bugün henüz bitmedi); görev başlangıcından
önceki günler sayılmaz.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Callable

from app.core.behavioral_settings import CHECKIN_MISSING_DAYS, WEEKLY_INTERVAL_DAYS
from app.repositories.behavioral import CheckinRepository, CognitiveTestRepository, WeeklyRepository
from app.schemas.behavioral_module import TodayCheckin, TodayOut, TodaySignals
from app.services.behavioral_calendar import consecutive_missing, is_test_day, mission_day
from app.services.behavioral_checkins import etag

TEST_TYPES = ("pvt", "rotation")
LOOKBACK_DAYS = 7
_MANY = 10_000          # repository list() sınırı; tek astronotun birkaç aylık kaydı için yeterli


class TodayService:
    def __init__(self, checkin_repo: CheckinRepository, test_repo: CognitiveTestRepository,
                 weekly_repo: WeeklyRepository, mission_start: date,
                 now: Callable[[], datetime]) -> None:
        self._checkins = checkin_repo
        self._tests = test_repo
        self._weekly = weekly_repo
        self._mission_start = mission_start
        self._now = now

    def today(self, astronaut_id: str) -> TodayOut:
        today = self._now().astimezone(timezone.utc).date()
        yesterday = today - timedelta(days=1)
        week_start = today - timedelta(days=LOOKBACK_DAYS)

        # check-in
        current = self._checkins.get_by_date(astronaut_id, today)
        checkin_dates = {r.date for r in self._checkins.list(
            astronaut_id, self._mission_start, today, _MANY, None)}
        consecutive = consecutive_missing(checkin_dates, yesterday, self._mission_start)
        past_week = [today - timedelta(days=k) for k in range(1, LOOKBACK_DAYS + 1)
                     if today - timedelta(days=k) >= self._mission_start]
        missed_7d = sum(1 for d in past_week if d not in checkin_dates)

        # testler
        today_types = {r.test_type for r in self._tests.list(astronaut_id, today, today, None, _MANY, None)}
        week_test_dates = {r.date for r in self._tests.list(
            astronaut_id, week_start, yesterday, None, _MANY, None)}
        week_test_days = [d for d in past_week if is_test_day(d, self._mission_start)]
        latest_test = self._tests.list(astronaut_id, None, today, None, 1, None)

        # haftalık ölçek (yalnız tarih)
        latest_weekly = self._weekly.get_latest(astronaut_id)
        weekly_last = latest_weekly.date if latest_weekly else None
        weekly_next = weekly_last + timedelta(days=WEEKLY_INTERVAL_DAYS) if weekly_last else None

        return TodayOut(
            date=today,
            mission_day=mission_day(today, self._mission_start),
            checkin=TodayCheckin(done=current is not None, etag=etag(current) if current else None),
            tests_due=list(TEST_TYPES) if is_test_day(today, self._mission_start) else [],
            tests_done=[t for t in TEST_TYPES if t in today_types],
            weekly_due=weekly_next is None or today >= weekly_next,
            weekly_last_date=weekly_last,
            weekly_next_date=weekly_next,
            signals=TodaySignals(
                checkin_missing=consecutive >= CHECKIN_MISSING_DAYS,
                consecutive_missed_checkin_days=consecutive,
                missed_checkin_days_7d=missed_7d,
                last_checkin_date=max(checkin_dates) if checkin_dates else None,
                tests_missing=bool(week_test_days) and not any(d in week_test_dates for d in week_test_days),
                last_test_date=latest_test[0].date if latest_test else None,
            ),
        )
