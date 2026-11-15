"""Haftalık ölçek servisi: puanlama, destek notu, 7 gün kuralı, tekrar gönderim, paylaşım, gizlilik."""
import logging
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest

from app.schemas.behavioral import WeeklyIn
from app.services.behavioral_errors import BehavioralError

A007, A008 = "A007", "A008"
NOW = datetime(2026, 11, 14, 9, 0, 0, tzinfo=timezone.utc)

# Sözleşme örneği: who5 3,2,3,2,2 -> 48; phq2 1,1 -> 2; gad2 2,1 -> 3
CONTRACT_ANSWERS = {"who5_1": 3, "who5_2": 2, "who5_3": 3, "who5_4": 2, "who5_5": 2,
                    "phq2_1": 1, "phq2_2": 1, "gad2_1": 2, "gad2_2": 1}
LOW_ANSWERS = {**CONTRACT_ANSWERS, "gad2_1": 1, "gad2_2": 0}            # phq2 2, gad2 1


def body(answers=None, crid: str | None = None, **changes) -> WeeklyIn:
    values = {"client_request_id": crid or str(uuid.uuid4()), "answers": answers or CONTRACT_ANSWERS}
    values.update(changes)
    return WeeklyIn.model_validate(values)


def assert_error(excinfo, code: str, status: int) -> None:
    err = excinfo.value
    assert (err.code, err.status) == (code, status)
    assert isinstance(err.message, str) and err.message


# ---------------------------------------------------------------- puanlama ve destek notu

def test_contract_example(weekly_service):
    out, created = weekly_service.submit(A007, body())
    assert created is True and out.id == 1
    assert (out.who5_score, out.phq2_score, out.gad2_score) == (48, 2, 3)
    assert out.support_note is True and out.share_with_crew_medical is False
    assert out.date == date(2026, 11, 14) and out.mission_day == 75
    assert out.created_at == NOW


def test_low_scores_no_support_note(weekly_service):
    out, _ = weekly_service.submit(A007, body(LOW_ANSWERS))
    assert (out.phq2_score, out.gad2_score) == (2, 1) and out.support_note is False


def test_share_true_on_submit(weekly_service):
    out, _ = weekly_service.submit(A007, body(share_with_crew_medical=True))
    assert out.share_with_crew_medical is True


def test_support_note_not_stored(weekly_service, weekly_repo):
    out, _ = weekly_service.submit(A007, body())
    assert not hasattr(weekly_repo.get_by_id(A007, out.id), "support_note")


# ---------------------------------------------------------------- 7 gün kuralı

def test_second_submit_before_seven_days(weekly_service, clock):
    weekly_service.submit(A007, body())
    clock.value = NOW + timedelta(days=6)
    with pytest.raises(BehavioralError) as excinfo:
        weekly_service.submit(A007, body())
    assert_error(excinfo, "weekly_not_due", 409)
    assert excinfo.value.message == "Next weekly assessment is due on 2026-11-21"


def test_submit_after_exactly_seven_days(weekly_service, clock):
    weekly_service.submit(A007, body())
    clock.value = NOW + timedelta(days=7)
    out, created = weekly_service.submit(A007, body())
    assert created is True and out.date == date(2026, 11, 21) and out.id == 2


def test_seven_day_rule_is_per_astronaut(weekly_service):
    weekly_service.submit(A007, body())
    out, created = weekly_service.submit(A008, body())
    assert created is True


def test_resubmit_same_request_id_after_three_days(weekly_service, clock):
    crid = str(uuid.uuid4())
    first, _ = weekly_service.submit(A007, body(crid=crid))
    clock.value = NOW + timedelta(days=3)
    again, created = weekly_service.submit(A007, body(crid=crid))
    assert created is False and again == first


# ---------------------------------------------------------------- paylaşım

def test_set_sharing(weekly_service):
    out, _ = weekly_service.submit(A007, body())
    shared = weekly_service.set_sharing(A007, out.id, True)
    assert shared.share_with_crew_medical is True
    assert shared.model_dump(exclude={"share_with_crew_medical"}) == \
        out.model_dump(exclude={"share_with_crew_medical"})
    assert weekly_service.set_sharing(A007, out.id, False).share_with_crew_medical is False


def test_set_sharing_other_astronaut_not_found(weekly_service):
    out, _ = weekly_service.submit(A007, body())
    with pytest.raises(BehavioralError) as excinfo:
        weekly_service.set_sharing(A008, out.id, True)
    assert_error(excinfo, "not_found", 404)
    assert weekly_service.list(A007, None, None).items[0].share_with_crew_medical is False


def test_set_sharing_missing_id_not_found(weekly_service):
    with pytest.raises(BehavioralError) as excinfo:
        weekly_service.set_sharing(A007, 999, True)
    assert_error(excinfo, "not_found", 404)


# ---------------------------------------------------------------- listeleme

@pytest.fixture
def three_weeks(weekly_service, clock):
    for week in range(3):
        clock.value = NOW + timedelta(days=7 * week)
        weekly_service.submit(A007, body())
    return weekly_service


def test_list_has_no_answers(three_weeks):
    page = three_weeks.list(A007, None, None)
    assert len(page.items) == 3
    for item in page.items:
        dumped = item.model_dump()
        assert "answers" not in dumped and not any(k.startswith(("who5_", "phq2_", "gad2_")) and
                                                   not k.endswith("_score") for k in dumped)


def test_list_pagination_newest_first(three_weeks):
    first = three_weeks.list(A007, None, None, limit=2)
    assert [i.date.day for i in first.items] == [28, 21] and first.next_cursor
    rest = three_weeks.list(A007, None, None, limit=2, cursor=first.next_cursor)
    assert [i.date.day for i in rest.items] == [14] and rest.next_cursor is None


def test_list_other_astronaut_empty(three_weeks):
    assert three_weeks.list(A008, None, None).items == []


@pytest.mark.parametrize("kwargs", [{"limit": 0}, {"limit": 101}, {"cursor": "bozuk"}])
def test_list_validation_errors(three_weeks, kwargs):
    with pytest.raises(BehavioralError) as excinfo:
        three_weeks.list(A007, None, None, **kwargs)
    assert_error(excinfo, "validation_error", 422)


# ---------------------------------------------------------------- gizlilik

def test_no_answers_or_scores_in_logs(weekly_service, caplog):
    caplog.set_level(logging.DEBUG)
    out, _ = weekly_service.submit(A007, body())
    weekly_service.list(A007, None, None)
    weekly_service.set_sharing(A007, out.id, True)
    forbidden = ["who5", "phq2", "gad2", str(out.who5_score)]
    for record in caplog.records:
        text = record.getMessage() + " " + str(record.args)
        assert not any(word in text for word in forbidden), text


def test_weekly_module_does_not_log():
    import app.services.behavioral_weekly as module
    source = open(module.__file__, encoding="utf-8").read()
    assert "import logging" not in source and "print(" not in source
