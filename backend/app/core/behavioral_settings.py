"""Davranışsal modül ayarları.

Demo için saati sabitlemek:  BEHAVIORAL_FIXED_NOW=2026-11-14T09:00:00Z
"""
from __future__ import annotations

import os
from datetime import date, datetime, timezone

# GEÇİCİ: ileride mission tablosundan okunacak.
MISSION_START = date(2026, 9, 1)

FIXED_NOW_ENV = "BEHAVIORAL_FIXED_NOW"


def utc_now() -> datetime:
    """BEHAVIORAL_FIXED_NOW (ISO 8601, saat dilimli) varsa onu, yoksa gerçek UTC saati döner."""
    fixed = os.environ.get(FIXED_NOW_ENV)
    if not fixed:
        return datetime.now(timezone.utc)
    value = datetime.fromisoformat(fixed.replace("Z", "+00:00"))
    if value.tzinfo is None:
        raise ValueError(f"{FIXED_NOW_ENV} must include a timezone, e.g. 2026-11-14T09:00:00Z")
    return value.astimezone(timezone.utc)


# Test günleri: seed_behavioral.py ile AYNI kural -> görev günü % 7 bu değerlerden biriyse.
# Görev 2026-09-01 (Salı) başladığı için bu Salı ve Cuma'ya denk gelir.
# (Takvim haftasının günü DEĞİL; görev başlangıcı değişirse günler de kayar.)
TEST_WEEKDAYS = frozenset({1, 4})

CHECKIN_MISSING_DAYS = 2        # bu kadar ardışık eksik gün -> checkin_missing
WEEKLY_INTERVAL_DAYS = 7
