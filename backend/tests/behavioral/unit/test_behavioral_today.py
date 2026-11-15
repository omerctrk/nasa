"""Bugün ekranı: check-in durumu, test günü, haftalık durum ve eksik veri sinyalleri."""
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from pydantic import TypeAdapter

from app.schemas.behavioral import CheckinIn, CognitiveTestIn, WeeklyIn

A007 = "A007"
NOW = datetime(2026, 11, 14, 9, 0, tzinfo=timezone.utc)          # görev günü 75, test günü değil
ADAPTER = TypeAdapter(CognitiveTestIn)
CHECKIN = CheckinIn.model_validate({"mood": 6, "energy": 5, "stress": 4, "loneliness": 1, "crew_relation": 3,
                                    "bed_time": "23:30", "wake_time": "06:45", "sleep_quality": 4})
WEEKLY_ANSWERS = {"who5_1": 3, "who5_2": 2, "who5_3": 3, "who5_4": 2, "who5_5": 2,
                  "phq2_1": 1, "phq2_2": 1, "gad2_1": 2, "gad2_2": 1}


def add_checkin(service, day: int, month: int = 11):
    service.put(A007, date(2026, month, day), CHECKIN, if_match=None, if_none_match="*")


def add_pvt(service, started_at: datetime, n: int = 40):
    service.submit(A007, ADAPTER.validate_python({
        "client_request_id": str(uuid.uuid4()), "test_type": "pvt",
        "started_at": started_at.isoformat(), "finished_at": (started_at + timedelta(minutes=3)).isoformat(),
        "trials": [{"i": i, "delay_ms": 2000, "rt_ms": 300, "false_start": False} for i in range(1, n + 1)],
    }))


def add_weekly(service, clock, at: datetime):
    saved = clock.value
    clock.value = at
    service.submit(A007, WeeklyIn.model_validate({"client_request_id": str(uuid.uuid4()),
                                                  "answers": WEEKLY_ANSWERS}))
    clock.value = saved


def test_no_data(today_service):
    out = today_service.today(A007)
    assert out.date == date(2026, 11, 14) and out.mission_day == 75
    assert out.checkin.done is False and out.checkin.etag is None
    assert out.weekly_due is True and out.weekly_last_date is None and out.weekly_next_date is None
    s = out.signals
    assert s.checkin_missing is True and s.consecutive_missed_checkin_days == 74
    assert s.missed_checkin_days_7d == 7 and s.last_checkin_date is None
    assert s.tests_missing is True and s.last_test_date is None


def test_checkin_done_today(today_service, checkin_service):
    add_checkin(checkin_service, 14)
    out = today_service.today(A007)
    assert out.checkin.done is True and out.checkin.etag == '"c-1-1"'
    assert out.signals.last_checkin_date == date(2026, 11, 14)


def test_two_missing_days_is_signal(today_service, checkin_service):
    add_checkin(checkin_service, 11)                         # 12 ve 13 yok
    s = today_service.today(A007).signals
    assert s.consecutive_missed_checkin_days == 2 and s.checkin_missing is True
    assert s.last_checkin_date == date(2026, 11, 11)


def test_one_missing_day_is_not_signal(today_service, checkin_service):
    add_checkin(checkin_service, 11)
    add_checkin(checkin_service, 12)                         # yalnız 13 yok
    s = today_service.today(A007).signals
    assert s.consecutive_missed_checkin_days == 1 and s.checkin_missing is False


def test_today_not_counted_as_missing(today_service, checkin_service):
    add_checkin(checkin_service, 13)                         # bugün (14) henüz yok
    s = today_service.today(A007).signals
    assert s.consecutive_missed_checkin_days == 0 and s.checkin_missing is False


def test_missed_days_in_last_week(today_service, checkin_service):
    for day in (7, 9, 11, 13):                               # 8, 10, 12 eksik
        add_checkin(checkin_service, day)
    assert today_service.today(A007).signals.missed_checkin_days_7d == 3


def test_tests_due_depends_on_day(today_service, clock):
    assert today_service.today(A007).tests_due == []                     # 14 Kasım, gün 75
    clock.value = datetime(2026, 11, 13, 9, 0, tzinfo=timezone.utc)      # 13 Kasım, gün 74
    assert today_service.today(A007).tests_due == ["pvt", "rotation"]


def test_tests_done_today(today_service, cognitive_service):
    add_pvt(cognitive_service, NOW - timedelta(minutes=20))
    out = today_service.today(A007)
    assert out.tests_done == ["pvt"] and out.signals.last_test_date == date(2026, 11, 14)


def test_invalid_test_counts_as_done(today_service, cognitive_service):
    add_pvt(cognitive_service, NOW - timedelta(minutes=20), n=5)          # geçersiz oturum
    assert today_service.today(A007).tests_done == ["pvt"]


def test_tests_missing_cleared_by_test_on_test_day(today_service, cognitive_service):
    add_pvt(cognitive_service, datetime(2026, 11, 13, 8, 0, tzinfo=timezone.utc))
    s = today_service.today(A007).signals
    assert s.tests_missing is False and s.last_test_date == date(2026, 11, 13)


def test_test_on_non_test_day_does_not_clear_signal(today_service, cognitive_service):
    add_pvt(cognitive_service, datetime(2026, 11, 12, 8, 0, tzinfo=timezone.utc))   # gün 73
    assert today_service.today(A007).signals.tests_missing is True


@pytest.mark.parametrize("days_ago,due,next_date", [
    (5, False, date(2026, 11, 16)),
    (7, True, date(2026, 11, 14)),
])
def test_weekly_due(today_service, weekly_service, clock, days_ago, due, next_date):
    add_weekly(weekly_service, clock, NOW - timedelta(days=days_ago))
    out = today_service.today(A007)
    assert out.weekly_due is due and out.weekly_next_date == next_date
    assert out.weekly_last_date == date(2026, 11, 14) - timedelta(days=days_ago)


def test_today_has_no_weekly_scores(today_service, weekly_service, clock):
    add_weekly(weekly_service, clock, NOW - timedelta(days=2))
    text = today_service.today(A007).model_dump_json()
    assert not any(word in text for word in ("who5", "phq2", "gad2", "answers", "share", "support"))


def test_mission_day_two_ignores_days_before_start(today_service, clock):
    clock.value = datetime(2026, 9, 2, 9, 0, tzinfo=timezone.utc)
    out = today_service.today(A007)
    assert out.mission_day == 2
    s = out.signals
    assert s.consecutive_missed_checkin_days == 1 and s.checkin_missing is False
    assert s.missed_checkin_days_7d == 1
    assert s.tests_missing is True                            # 1 Eylül test günüydü


def test_mission_day_one_has_no_missing(today_service, clock):
    clock.value = datetime(2026, 9, 1, 9, 0, tzinfo=timezone.utc)
    s = today_service.today(A007).signals
    assert s.consecutive_missed_checkin_days == 0 and s.missed_checkin_days_7d == 0
    assert s.checkin_missing is False and s.tests_missing is False


def test_other_astronaut_data_ignored(today_service, checkin_service):
    add_checkin(checkin_service, 14)
    assert today_service.today("A008").checkin.done is False
