"""Anomali modülüne giden günlük metrikler."""
import inspect
import uuid
from datetime import date, datetime, timedelta, timezone
from statistics import mean

import pytest
from pydantic import TypeAdapter

from app.repositories.behavioral_seed_loader import load_seed_rows
from app.schemas.behavioral import CheckinIn, CognitiveTestIn
from app.services.behavioral_errors import BehavioralError
from app.services.behavioral_feed import DailyMetrics, DailyMetricsFeed

A007 = "A007"
ADAPTER = TypeAdapter(CognitiveTestIn)
EXPECTED_KEYS = [
    "date", "mission_day", "checkin_done",
    "mood_index", "stress", "loneliness", "crew_relation", "sleep_hours", "sleep_quality",
    "symptoms",
    "pvt_mean_rt_ms", "pvt_lapses", "pvt_false_starts",
    "rotation_accuracy", "rotation_mean_rt_ms",
    "checkin_missing",
]


def add_checkin(service, day: int, **changes):
    values = {"mood": 6, "energy": 5, "stress": 4, "loneliness": 1, "crew_relation": 3,
              "bed_time": "23:30", "wake_time": "06:45", "sleep_quality": 4, **changes}
    service.put(A007, date(2026, 11, day), CheckinIn.model_validate(values), if_match=None, if_none_match="*")


def add_pvt(service, started_at: datetime, rt: float = 300, n: int = 40):
    service.submit(A007, ADAPTER.validate_python({
        "client_request_id": str(uuid.uuid4()), "test_type": "pvt",
        "started_at": started_at.isoformat(), "finished_at": (started_at + timedelta(minutes=3)).isoformat(),
        "trials": [{"i": i, "delay_ms": 2000, "rt_ms": rt, "false_start": False} for i in range(1, n + 1)],
    }))


def add_rotation(service, started_at: datetime):
    trials = [{"i": i, "shape": "s1", "angle": 0, "mirror": i % 2 == 0,
               "answer": "mirror" if i % 2 == 0 else "same", "rt_ms": 1500} for i in range(1, 17)]
    service.submit(A007, ADAPTER.validate_python({
        "client_request_id": str(uuid.uuid4()), "test_type": "rotation",
        "started_at": started_at.isoformat(), "finished_at": (started_at + timedelta(minutes=2)).isoformat(),
        "trials": trials,
    }))


def at(day: int, hour: int = 8, minute: int = 0) -> datetime:
    return datetime(2026, 11, day, hour, minute, tzinfo=timezone.utc)


def test_one_row_per_day_with_nulls(metrics_feed, checkin_service):
    for day in (10, 11, 13):
        add_checkin(checkin_service, day, symptoms=["headache"])
    rows = metrics_feed.daily_metrics(A007, date(2026, 11, 10), date(2026, 11, 14))
    assert [r.date.day for r in rows] == [10, 11, 12, 13, 14]
    assert [r.mission_day for r in rows] == [71, 72, 73, 74, 75]
    gap = rows[2]
    assert gap.checkin_done is False and gap.symptoms == []
    assert all(getattr(gap, k) is None for k in ("mood_index", "stress", "loneliness", "crew_relation",
                                                 "sleep_hours", "sleep_quality", "pvt_mean_rt_ms"))
    full = rows[0]
    assert full.checkin_done is True and full.mood_index == 56.7 and full.sleep_hours == 7.25
    assert full.symptoms == ["headache"]


def test_checkin_missing_per_day(metrics_feed, checkin_service):
    add_checkin(checkin_service, 10)
    rows = metrics_feed.daily_metrics(A007, date(2026, 11, 10), date(2026, 11, 14))
    assert [r.checkin_missing for r in rows] == [False, False, True, True, True]


def test_today_row_not_counted_as_missing(metrics_feed, checkin_service):
    add_checkin(checkin_service, 13)
    assert metrics_feed.daily_metrics(A007, date(2026, 11, 14), date(2026, 11, 14))[0].checkin_missing is False


def test_invalid_test_not_used(metrics_feed, cognitive_service):
    add_pvt(cognitive_service, at(13), n=5)                  # geçersiz: too_few_responses
    row = metrics_feed.daily_metrics(A007, date(2026, 11, 13), date(2026, 11, 13))[0]
    assert row.pvt_mean_rt_ms is None and row.pvt_lapses is None


def test_latest_valid_test_of_day_used(metrics_feed, cognitive_service):
    add_pvt(cognitive_service, at(13, 8), rt=300)
    add_pvt(cognitive_service, at(13, 10), rt=320)          # aynı gün, daha sonra
    add_pvt(cognitive_service, at(13, 11), rt=500, n=5)     # en son ama geçersiz
    add_rotation(cognitive_service, at(13, 9))
    row = metrics_feed.daily_metrics(A007, date(2026, 11, 13), date(2026, 11, 13))[0]
    assert row.pvt_mean_rt_ms == 320.0 and row.pvt_lapses == 0 and row.pvt_false_starts == 0
    assert row.rotation_accuracy == 1.0 and row.rotation_mean_rt_ms == 1500.0


def test_row_keys_exact(metrics_feed, checkin_service):
    add_checkin(checkin_service, 14)
    rows = metrics_feed.daily_metrics(A007, date(2026, 11, 13), date(2026, 11, 14))
    assert list(DailyMetrics.model_fields) == EXPECTED_KEYS
    for row in rows:
        assert list(row.model_dump()) == EXPECTED_KEYS


def test_no_weekly_data_in_feed(metrics_feed, checkin_service):
    add_checkin(checkin_service, 14)
    text = "".join(r.model_dump_json() for r in metrics_feed.daily_metrics(A007, date(2026, 11, 1),
                                                                          date(2026, 11, 14)))
    assert not any(word in text for word in ("who5", "phq2", "gad2", "answers", "share"))
    params = inspect.signature(DailyMetricsFeed.__init__).parameters
    assert not any("weekly" in name for name in params)


@pytest.mark.parametrize("date_from,date_to,code,status", [
    (date(2026, 11, 13), date(2026, 11, 10), "validation_error", 422),
    (date(2026, 8, 31), date(2026, 9, 2), "validation_error", 422),
    (date(2026, 11, 13), date(2026, 11, 15), "future_date", 422),
])
def test_invalid_ranges(metrics_feed, date_from, date_to, code, status):
    with pytest.raises(BehavioralError) as excinfo:
        metrics_feed.daily_metrics(A007, date_from, date_to)
    assert (excinfo.value.code, excinfo.value.status) == (code, status)


def test_seed_scenario(metrics_feed, checkin_repo, cognitive_repo, weekly_repo):
    from scripts.seed_behavioral import generate
    load_seed_rows(generate(), checkin_repo, cognitive_repo, weekly_repo)
    rows = metrics_feed.daily_metrics(A007, date(2026, 9, 1), date(2026, 11, 13))
    assert len(rows) == 74 and rows[0].mission_day == 1 and rows[-1].mission_day == 74
    assert all(r.checkin_done for r in rows) and not any(r.checkin_missing for r in rows)
    stable = mean(r.mood_index for r in rows if r.mission_day <= 60)
    late = mean(r.mood_index for r in rows if r.mission_day >= 61)
    assert late < stable
    pvt_days = [r for r in rows if r.pvt_mean_rt_ms is not None]
    assert pvt_days and all(r.mission_day % 7 in (1, 4) for r in pvt_days)
