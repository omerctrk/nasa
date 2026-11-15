"""Bilişsel test servisi: puanlama, tekrar gönderim, tarih kuralları, okuma ve listeleme."""
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from pydantic import TypeAdapter

from app.schemas.behavioral_module import CognitiveTestIn
from app.services.behavioral_errors import BehavioralError

A007, A008 = "A007", "A008"
NOW = datetime(2026, 11, 14, 9, 0, 0, tzinfo=timezone.utc)
ADAPTER = TypeAdapter(CognitiveTestIn)


def assert_error(excinfo, code: str, status: int, fields=None) -> None:
    err = excinfo.value
    assert (err.code, err.status) == (code, status)
    assert isinstance(err.message, str) and err.message
    if fields is not None:
        assert err.fields == fields


def pvt_trials(n: int = 40, rt: float = 300, false_starts: int = 0) -> list[dict]:
    trials = [{"i": i, "delay_ms": 2000, "rt_ms": rt, "false_start": False} for i in range(1, n + 1)]
    for t in trials[:false_starts]:
        t.update(rt_ms=None, false_start=True)
    return trials


def rotation_trials(correct: int = 16) -> list[dict]:
    trials = []
    for i in range(1, 17):
        mirror = i % 2 == 0
        truth = "mirror" if mirror else "same"
        wrong = "same" if mirror else "mirror"
        trials.append({"i": i, "shape": "s1", "angle": (0, 60, 120, 180)[i % 4], "mirror": mirror,
                       "answer": truth if i <= correct else wrong, "rt_ms": 1500})
    return trials


def make(test_type: str, trials: list[dict], started_at: datetime = NOW - timedelta(minutes=10),
         crid: str | None = None, **changes):
    body = {
        "client_request_id": crid or str(uuid.uuid4()), "test_type": test_type,
        "started_at": started_at.isoformat(), "finished_at": (started_at + timedelta(minutes=3)).isoformat(),
        "device": "tablet-1", "trials": trials,
    }
    body.update(changes)
    return ADAPTER.validate_python(body)


def pvt(**kwargs):
    trials = kwargs.pop("trials", None)
    return make("pvt", pvt_trials() if trials is None else trials, **kwargs)


def rotation(correct: int = 16, **kwargs):
    return make("rotation", rotation_trials(correct), **kwargs)


# ---------------------------------------------------------------- PVT

def test_valid_pvt(cognitive_service):
    out, created = cognitive_service.submit(A007, pvt())
    assert created is True and out.id == 1
    assert out.valid is True and out.invalid_reason is None
    assert out.test_type == "pvt" and out.n_trials == 40 and out.mean_rt_ms == 300.0
    assert out.accuracy is None
    assert out.date == date(2026, 11, 14) and out.mission_day == 75
    assert out.source == "manual" and out.device == "tablet-1"
    assert not hasattr(out, "correct_count") and not hasattr(out, "trials")


def test_resubmit_same_request_id_returns_first(cognitive_service, cognitive_repo):
    crid = str(uuid.uuid4())
    first, _ = cognitive_service.submit(A007, pvt(crid=crid))
    again, created = cognitive_service.submit(A007, pvt(crid=crid))
    assert created is False and again == first
    different, created = cognitive_service.submit(A007, pvt(crid=crid, trials=pvt_trials(n=5)))
    assert created is False and different == first and different.n_trials == 40
    assert len(cognitive_repo.list(A007, None, None, None, 100, None)) == 1


def test_same_request_id_other_astronaut_is_separate(cognitive_service):
    crid = str(uuid.uuid4())
    first, _ = cognitive_service.submit(A007, pvt(crid=crid))
    other, created = cognitive_service.submit(A008, pvt(crid=crid))
    assert created is True and other.id != first.id


def test_pvt_too_few_responses_is_saved(cognitive_service):
    out, created = cognitive_service.submit(A007, pvt(trials=pvt_trials(n=10)))
    assert created is True and out.valid is False and out.invalid_reason == "too_few_responses"
    assert cognitive_service.get(A007, out.id).valid is False


def test_pvt_too_many_false_starts(cognitive_service):
    out, _ = cognitive_service.submit(A007, pvt(trials=pvt_trials(n=50, false_starts=15)))
    assert out.valid is False and out.invalid_reason == "too_many_false_starts"
    assert out.false_starts == 15


@pytest.mark.parametrize("test_type", ["pvt", "rotation"])
def test_empty_trials_no_trials(cognitive_service, test_type):
    out, created = cognitive_service.submit(A007, make(test_type, []))
    assert created is True and out.valid is False and out.invalid_reason == "no_trials"
    assert out.n_trials == 0


# ---------------------------------------------------------------- döndürme

def test_rotation_all_correct(cognitive_service):
    out, _ = cognitive_service.submit(A007, rotation(correct=16))
    assert out.valid is True and out.accuracy == 1.0 and out.mean_rt_ms == 1500.0
    assert out.median_rt_ms is None and out.speed is None
    assert out.lapses is None and out.false_starts is None


def test_rotation_near_chance(cognitive_service):
    out, _ = cognitive_service.submit(A007, rotation(correct=8))
    assert out.valid is False and out.invalid_reason == "near_chance_accuracy" and out.accuracy == 0.5


# ---------------------------------------------------------------- tarih kuralları

def test_started_at_in_future_rejected(cognitive_service):
    with pytest.raises(BehavioralError) as excinfo:
        cognitive_service.submit(A007, pvt(started_at=NOW + timedelta(minutes=10)))
    assert_error(excinfo, "future_date", 422, ["started_at"])


def test_started_at_within_clock_tolerance_accepted(cognitive_service):
    out, created = cognitive_service.submit(A007, pvt(started_at=NOW + timedelta(minutes=4)))
    assert created is True


def test_started_before_mission_rejected(cognitive_service):
    with pytest.raises(BehavioralError) as excinfo:
        cognitive_service.submit(A007, pvt(started_at=datetime(2026, 8, 31, 9, 0, tzinfo=timezone.utc)))
    assert_error(excinfo, "validation_error", 422)


def test_date_is_utc_day_of_started_at(cognitive_service):
    local = datetime(2026, 11, 14, 1, 30, tzinfo=timezone(timedelta(hours=3)))   # UTC: 13 Kasım 22:30
    out, _ = cognitive_service.submit(A007, pvt(started_at=local))
    assert out.date == date(2026, 11, 13) and out.mission_day == 74
    assert out.started_at.utcoffset() == timedelta(0)


# ---------------------------------------------------------------- okuma

def test_get_returns_trials(cognitive_service):
    out, _ = cognitive_service.submit(A007, rotation())
    detail = cognitive_service.get(A007, out.id)
    assert len(detail.trials) == 16 and detail.trials[0].shape == "s1"
    assert detail.model_dump(exclude={"trials"}) == out.model_dump()


def test_get_other_astronauts_test_not_found(cognitive_service):
    out, _ = cognitive_service.submit(A007, pvt())
    with pytest.raises(BehavioralError) as excinfo:
        cognitive_service.get(A008, out.id)
    assert_error(excinfo, "not_found", 404)


def test_get_missing_id_not_found(cognitive_service):
    with pytest.raises(BehavioralError) as excinfo:
        cognitive_service.get(A007, 999)
    assert_error(excinfo, "not_found", 404)


# ---------------------------------------------------------------- listeleme

@pytest.fixture
def five_tests(cognitive_service):
    """3 PVT + 2 döndürme, 10 Kasım - 14 Kasım, her gün bir test."""
    for day, kind in zip((10, 11, 12, 13, 14), ("pvt", "rotation", "pvt", "rotation", "pvt")):
        started = datetime(2026, 11, day, 8, 0, tzinfo=timezone.utc)
        body = pvt(started_at=started) if kind == "pvt" else rotation(started_at=started)
        cognitive_service.submit(A007, body)
    return cognitive_service


def test_list_has_no_trials(five_tests):
    page = five_tests.list(A007, None, None)
    assert len(page.items) == 5
    assert all("trials" not in item.model_dump() for item in page.items)


def test_list_filter_by_test_type(five_tests):
    page = five_tests.list(A007, None, None, test_type="rotation")
    assert [i.test_type for i in page.items] == ["rotation", "rotation"]
    assert [i.date.day for i in page.items] == [13, 11]


def test_list_pagination_newest_first(five_tests):
    first = five_tests.list(A007, None, None, limit=2)
    assert [i.date.day for i in first.items] == [14, 13] and first.next_cursor
    second = five_tests.list(A007, None, None, limit=2, cursor=first.next_cursor)
    assert [i.date.day for i in second.items] == [12, 11] and second.next_cursor
    last = five_tests.list(A007, None, None, limit=2, cursor=second.next_cursor)
    assert [i.date.day for i in last.items] == [10] and last.next_cursor is None


def test_list_same_started_at_ordered_by_id(cognitive_service):
    started = datetime(2026, 11, 14, 8, 0, tzinfo=timezone.utc)
    ids = [cognitive_service.submit(A007, pvt(started_at=started))[0].id for _ in range(3)]
    first = cognitive_service.list(A007, None, None, limit=2)
    second = cognitive_service.list(A007, None, None, limit=2, cursor=first.next_cursor)
    assert [i.id for i in first.items + second.items] == sorted(ids, reverse=True)


def test_list_from_to_inclusive(five_tests):
    page = five_tests.list(A007, date(2026, 11, 11), date(2026, 11, 13))
    assert [i.date.day for i in page.items] == [13, 12, 11]


def test_list_other_astronaut_empty(five_tests):
    assert five_tests.list(A008, None, None).items == []


@pytest.mark.parametrize("kwargs,fields", [
    ({"test_type": "dsst"}, ["test_type"]),
    ({"limit": 0}, ["limit"]),
    ({"limit": 101}, ["limit"]),
    ({"cursor": "bozuk"}, ["cursor"]),
])
def test_list_validation_errors(five_tests, kwargs, fields):
    with pytest.raises(BehavioralError) as excinfo:
        five_tests.list(A007, None, None, **kwargs)
    assert_error(excinfo, "validation_error", 422, fields)


def test_list_from_after_to(five_tests):
    with pytest.raises(BehavioralError) as excinfo:
        five_tests.list(A007, date(2026, 11, 13), date(2026, 11, 11))
    assert_error(excinfo, "validation_error", 422)
