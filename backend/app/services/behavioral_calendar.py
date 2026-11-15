"""Görev takvimi yardımcıları: görev günü, test günü, ardışık eksik gün sayımı."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Collection

from app.core.behavioral_settings import TEST_WEEKDAYS


def mission_day(d: date, mission_start: date) -> int:
    return (d - mission_start).days + 1


def is_test_day(d: date, mission_start: date) -> bool:
    return d >= mission_start and mission_day(d, mission_start) % 7 in TEST_WEEKDAYS


def consecutive_missing(checkin_dates: Collection[date], last_day: date, mission_start: date) -> int:
    """last_day dahil geriye doğru, ilk check-in'e veya görev başlangıcına kadar eksik gün sayısı."""
    count, d = 0, last_day
    while d >= mission_start and d not in checkin_dates:
        count += 1
        d -= timedelta(days=1)
    return count
