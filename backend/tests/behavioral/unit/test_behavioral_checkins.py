"""Check-in servisi: tarih kuralları, ön koşul başlıkları, ETag, tekrar gönderim, listeleme."""
from datetime import date, datetime, timedelta, timezone

import pytest

from app.schemas.behavioral import CheckinIn
from app.services.behavioral_errors import BehavioralError

A007, A008 = "A007", "A008"
TODAY = date(2026, 11, 14)
NOW = datetime(2026, 11, 14, 9, 0, 0, tzinfo=timezone.utc)
ANY = "*"


def body(**changes) -> CheckinIn:
    values = {"mood": 6, "energy": 5, "stress": 4, "loneliness": 1, "crew_relation": 3,
              "bed_time": "23:30", "wake_time": "06:45", "sleep_quality": 4}
    values.update(changes)
    return CheckinIn.model_validate(values)


def create(service, d=TODAY, astronaut_id=A007, **changes):
    return service.put(astronaut_id, d, body(**changes), if_match=None, if_none_match=ANY)


def assert_error(excinfo, code: str, status: int, fields=None) -> None:
    err = excinfo.value
    assert (err.code, err.status) == (code, status)
    assert isinstance(err.message, str) and err.message
    if fields is not None:
        assert err.fields == fields


# ---------------------------------------------------------------- görev günü

@pytest.mark.parametrize("d,expected", [
    (date(2026, 9, 1), 1), (date(2026, 11, 13), 74), (date(2026, 11, 14), 75),
])
def test_mission_day(checkin_service, d, expected):
    assert checkin_service.mission_day(d) == expected


# ---------------------------------------------------------------- oluşturma

def test_create_new_checkin(checkin_service):
    out, tag, created = create(checkin_service)
    assert created is True and tag == '"c-1-1"'
    assert out.id == 1 and out.date == TODAY and out.mission_day == 75
    assert out.mood_index == 56.7 and out.sleep_hours == 7.25
    assert out.symptoms == [] and out.source == "manual"
    assert out.created_at == NOW and out.updated_at == NOW


def test_create_same_day_different_body_is_mismatch(checkin_service):
    create(checkin_service)
    with pytest.raises(BehavioralError) as excinfo:
        create(checkin_service, mood=2)
    assert_error(excinfo, "etag_mismatch", 412)


def test_resubmit_same_body_returns_existing(checkin_service, checkin_repo, clock):
    first, first_tag, _ = create(checkin_service)
    clock.value = NOW + timedelta(minutes=5)
    out, tag, created = create(checkin_service)
    assert created is False and tag == first_tag == '"c-1-1"'
    assert out == first and out.updated_at == NOW
    assert checkin_repo.get_by_date(A007, TODAY).version == 1


def test_resubmit_same_body_ignores_stale_if_match(checkin_service):
    create(checkin_service)
    out, tag, created = checkin_service.put(A007, TODAY, body(), if_match='"c-1-9"', if_none_match=None)
    assert created is False and tag == '"c-1-1"'


# ---------------------------------------------------------------- güncelleme

def test_update_with_matching_etag(checkin_service, clock):
    first, tag, _ = create(checkin_service)
    later = NOW + timedelta(hours=1)
    clock.value = later
    out, new_tag, created = checkin_service.put(
        A007, TODAY, body(mood=8, symptoms=["headache"]), if_match=tag, if_none_match=None)
    assert created is False and new_tag == '"c-1-2"'
    assert out.id == first.id and out.mood == 8 and out.symptoms == ["headache"]
    assert out.created_at == NOW and out.updated_at == later
    assert out.mood_index == 63.3 and out.mood_index != first.mood_index


def test_update_with_stale_etag_is_mismatch(checkin_service):
    _, old_tag, _ = create(checkin_service)
    checkin_service.put(A007, TODAY, body(mood=8), if_match=old_tag, if_none_match=None)
    with pytest.raises(BehavioralError) as excinfo:
        checkin_service.put(A007, TODAY, body(mood=3), if_match=old_tag, if_none_match=None)
    assert_error(excinfo, "etag_mismatch", 412)


@pytest.mark.parametrize("if_match", ['"c-1-1"', ANY])
def test_if_match_without_record_is_mismatch(checkin_service, if_match):
    with pytest.raises(BehavioralError) as excinfo:
        checkin_service.put(A007, TODAY, body(), if_match=if_match, if_none_match=None)
    assert_error(excinfo, "etag_mismatch", 412)


def test_if_match_star_updates_existing(checkin_service):
    create(checkin_service)
    out, tag, created = checkin_service.put(A007, TODAY, body(stress=9), if_match=ANY, if_none_match=None)
    assert created is False and tag == '"c-1-2"' and out.stress == 9


# ---------------------------------------------------------------- ön koşul ve tarih

@pytest.mark.parametrize("if_match,if_none_match", [(None, None), ('"c-1-1"', ANY)])
def test_precondition_required(checkin_service, if_match, if_none_match):
    with pytest.raises(BehavioralError) as excinfo:
        checkin_service.put(A007, TODAY, body(), if_match=if_match, if_none_match=if_none_match)
    assert_error(excinfo, "precondition_required", 428)


def test_future_date_rejected(checkin_service):
    with pytest.raises(BehavioralError) as excinfo:
        create(checkin_service, d=date(2026, 11, 15))
    assert_error(excinfo, "future_date", 422, ["date"])


def test_date_before_mission_start_rejected(checkin_service):
    with pytest.raises(BehavioralError) as excinfo:
        create(checkin_service, d=date(2026, 8, 31))
    assert_error(excinfo, "validation_error", 422, ["date"])


# ---------------------------------------------------------------- okuma

def test_get_returns_record_and_etag(checkin_service):
    created, tag, _ = create(checkin_service)
    assert checkin_service.get(A007, TODAY) == (created, tag)


def test_get_missing_day(checkin_service):
    with pytest.raises(BehavioralError) as excinfo:
        checkin_service.get(A007, TODAY)
    assert_error(excinfo, "checkin_not_found", 404)


def test_other_astronaut_cannot_see_record(checkin_service):
    create(checkin_service)
    with pytest.raises(BehavioralError) as excinfo:
        checkin_service.get(A008, TODAY)
    assert_error(excinfo, "checkin_not_found", 404)


def test_astronauts_have_separate_records_for_same_day(checkin_service):
    create(checkin_service, mood=6)
    out, tag, created = create(checkin_service, astronaut_id=A008, mood=2)
    assert created is True and tag == '"c-2-1"'
    assert checkin_service.get(A007, TODAY)[0].mood == 6
    assert checkin_service.get(A008, TODAY)[0].mood == 2


# ---------------------------------------------------------------- listeleme

FIVE_DAYS = [date(2026, 11, d) for d in (10, 11, 12, 13, 14)]


@pytest.fixture
def five_days(checkin_service):
    for d in FIVE_DAYS:
        create(checkin_service, d=d)
    return checkin_service


def dates(page) -> list[date]:
    return [item.date for item in page.items]


def test_list_pagination(five_days):
    first = five_days.list(A007, None, None, limit=2)
    assert dates(first) == [date(2026, 11, 14), date(2026, 11, 13)] and first.next_cursor
    second = five_days.list(A007, None, None, limit=2, cursor=first.next_cursor)
    assert dates(second) == [date(2026, 11, 12), date(2026, 11, 11)] and second.next_cursor
    last = five_days.list(A007, None, None, limit=2, cursor=second.next_cursor)
    assert dates(last) == [date(2026, 11, 10)] and last.next_cursor is None


def test_list_exact_page_has_no_cursor(five_days):
    page = five_days.list(A007, None, None, limit=5)
    assert len(page.items) == 5 and page.next_cursor is None


def test_list_newest_first_with_default_limit(five_days):
    assert dates(five_days.list(A007, None, None)) == sorted(FIVE_DAYS, reverse=True)


def test_list_from_and_to_inclusive(five_days):
    page = five_days.list(A007, date(2026, 11, 11), date(2026, 11, 13))
    assert dates(page) == [date(2026, 11, 13), date(2026, 11, 12), date(2026, 11, 11)]


@pytest.mark.parametrize("limit", [0, 101])
def test_list_limit_out_of_range(five_days, limit):
    with pytest.raises(BehavioralError) as excinfo:
        five_days.list(A007, None, None, limit=limit)
    assert_error(excinfo, "validation_error", 422, ["limit"])


def test_list_from_after_to(five_days):
    with pytest.raises(BehavioralError) as excinfo:
        five_days.list(A007, date(2026, 11, 13), date(2026, 11, 11))
    assert_error(excinfo, "validation_error", 422)


@pytest.mark.parametrize("cursor", ["not-a-cursor", "", "MjAyNi0xMy00NQ=="])   # sonuncusu: "2026-13-45"
def test_list_broken_cursor(five_days, cursor):
    with pytest.raises(BehavioralError) as excinfo:
        five_days.list(A007, None, None, cursor=cursor)
    assert_error(excinfo, "validation_error", 422, ["cursor"])


def test_list_empty_for_other_astronaut(five_days):
    page = five_days.list(A008, None, None)
    assert page.items == [] and page.next_cursor is None
