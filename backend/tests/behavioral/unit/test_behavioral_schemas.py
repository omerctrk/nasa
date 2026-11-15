"""Davranışsal modül Pydantic şemalarının kabul / ret kuralları."""
import copy

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas.behavioral_module import (
    CheckinIn, CognitiveTestIn, ErrorResponse, Page, PvtTestIn, RotationTestIn, WeeklyIn,
)

TEST_ADAPTER = TypeAdapter(CognitiveTestIn)
REQUEST_ID = "3f2b8c1e-9d4a-4c7b-8e21-5a6f7d8c9b10"   # UUID4


def checkin(**changes) -> dict:
    body = {
        "mood": 6, "energy": 5, "stress": 4, "loneliness": 1, "crew_relation": 3,
        "bed_time": "23:30", "wake_time": "06:45", "sleep_quality": 4,
        "symptoms": ["headache", "fatigue"],
    }
    body.update(changes)
    return body


def pvt_trials() -> list[dict]:
    return [
        {"i": 1, "delay_ms": 2340, "rt_ms": 287, "false_start": False},    # normal
        {"i": 2, "delay_ms": 3100, "rt_ms": None, "false_start": False},   # cevapsız
        {"i": 3, "delay_ms": 1500, "rt_ms": None, "false_start": True},    # erken basma
    ]


def rotation_trials(n: int = 16) -> list[dict]:
    trials = []
    for i in range(1, n + 1):
        mirror = i % 2 == 0
        trials.append({"i": i, "shape": f"s{i % 4 + 1}", "angle": (0, 60, 120, 180)[i % 4],
                       "mirror": mirror, "answer": "mirror" if mirror else "same", "rt_ms": 1500})
    trials[0].update(answer=None, rt_ms=None)                              # cevapsız
    return trials


def make_body(test_type: str, trials: list[dict], /, **changes) -> dict:
    body = {
        "client_request_id": REQUEST_ID, "test_type": test_type,
        "started_at": "2026-11-14T09:00:00Z", "finished_at": "2026-11-14T09:03:00Z",
        "device": "tablet-1", "trials": trials,
    }
    body.update(changes)
    return body



def pvt_body(**changes) -> dict:
    return make_body("pvt", pvt_trials(), **changes)


def rotation_body(**changes) -> dict:
    return make_body("rotation", rotation_trials(), **changes)


def with_trial(body: dict, index: int = 0, **changes) -> dict:
    body = copy.deepcopy(body)
    body["trials"][index].update(changes)
    return body


def weekly(share=..., **answer_changes) -> dict:
    answers = {"who5_1": 3, "who5_2": 4, "who5_3": 3, "who5_4": 2, "who5_5": 4,
               "phq2_1": 0, "phq2_2": 1, "gad2_1": 1, "gad2_2": 0}
    for key, value in answer_changes.items():
        if value is ...:
            del answers[key]
        else:
            answers[key] = value
    body = {"client_request_id": REQUEST_ID, "answers": answers}
    if share is not ...:
        body["share_with_crew_medical"] = share
    return body


# ---------------------------------------------------------------- kabul edilenler

def test_checkin_valid():
    m = CheckinIn.model_validate(checkin())
    assert m.symptoms == ["headache", "fatigue"] and m.crew_relation == 3
    assert m.bed_time == "23:30" and m.wake_time == "06:45"


def test_checkin_symptoms_default_empty():
    body = checkin()
    del body["symptoms"]
    assert CheckinIn.model_validate(body).symptoms == []


def test_pvt_valid_three_trials():
    m = TEST_ADAPTER.validate_python(pvt_body())
    assert isinstance(m, PvtTestIn) and len(m.trials) == 3
    assert m.trials[1].rt_ms is None and m.trials[2].false_start is True


def test_pvt_accepts_fast_response_below_100_ms():
    m = TEST_ADAPTER.validate_python(with_trial(pvt_body(), 0, rt_ms=64))
    assert m.trials[0].rt_ms == 64


def test_rotation_valid_sixteen_trials():
    m = TEST_ADAPTER.validate_python(rotation_body())
    assert isinstance(m, RotationTestIn) and len(m.trials) == 16
    assert m.trials[0].answer is None and m.trials[0].rt_ms is None


@pytest.mark.parametrize("test_type", ["pvt", "rotation"])
def test_empty_trials_accepted(test_type):
    assert TEST_ADAPTER.validate_python(make_body(test_type, [])).trials == []


def test_weekly_share_defaults_false():
    m = WeeklyIn.model_validate(weekly())
    assert m.share_with_crew_medical is False and m.answers.who5_1 == 3


def test_page_generic():
    page = Page[int].model_validate({"items": [1, 2], "next_cursor": None})
    assert page.items == [1, 2] and page.next_cursor is None


def test_error_response_shape():
    body = {"detail": {"code": "validation_error", "message": "Invalid request body",
                       "fields": ["mood", "bed_time"]}}
    assert ErrorResponse.model_validate(body).model_dump() == body
    minimal = ErrorResponse.model_validate({"detail": {"code": "not_found", "message": "Not found"}})
    assert minimal.model_dump() == {"detail": {"code": "not_found", "message": "Not found", "fields": []}}


# ---------------------------------------------------------------- reddedilenler

CHECKIN_REJECTS = {
    "mood_11": checkin(mood=11),
    "mood_negative": checkin(mood=-1),
    "mood_bool": checkin(mood=True),
    "mood_string": checkin(mood="6"),
    "mood_float": checkin(mood=6.5),
    "crew_key": checkin(crew=3),
    "astronaut_id_key": checkin(astronaut_id="A007"),
    "unknown_symptom": checkin(symptoms=["bas_agrisi"]),
    "duplicate_symptom": checkin(symptoms=["headache", "headache"]),
    "bed_time_24_00": checkin(bed_time="24:00"),
    "bed_time_with_seconds": checkin(bed_time="23:30:00"),
    "bed_time_no_leading_zero": checkin(bed_time="7:30"),
    "sleep_quality_0": checkin(sleep_quality=0),
}


@pytest.mark.parametrize("body", CHECKIN_REJECTS.values(), ids=CHECKIN_REJECTS.keys())
def test_checkin_rejected(body):
    with pytest.raises(ValidationError):
        CheckinIn.model_validate(body)


def _seventeen_trials() -> dict:
    body = rotation_body()
    body["trials"].append({"i": 17, "shape": "s1", "angle": 0, "mirror": False,
                           "answer": "same", "rt_ms": 1500})
    return body


TEST_REJECTS = {
    "angle_90": with_trial(rotation_body(), 1, angle=90),
    "shape_s5": with_trial(rotation_body(), 1, shape="s5"),
    "answer_left": with_trial(rotation_body(), 1, answer="left"),
    "answer_null_with_rt": with_trial(rotation_body(), 0, rt_ms=1500),
    "false_start_with_rt": with_trial(pvt_body(), 2, rt_ms=64),
    "delay_ms_500": with_trial(pvt_body(), 0, delay_ms=500),
    "test_type_dsst": pvt_body(test_type="dsst"),
    "rotation_17_trials": _seventeen_trials(),
    "duplicate_trial_index": with_trial(rotation_body(), 1, i=1),
    "naive_started_at": pvt_body(started_at="2026-11-14T09:00:00"),
    "finished_before_started": pvt_body(finished_at="2026-11-14T08:59:59Z"),
    "client_request_id_abc": pvt_body(client_request_id="abc"),
}


@pytest.mark.parametrize("body", TEST_REJECTS.values(), ids=TEST_REJECTS.keys())
def test_cognitive_test_rejected(body):
    with pytest.raises(ValidationError):
        TEST_ADAPTER.validate_python(body)


WEEKLY_REJECTS = {
    "who5_1_missing": weekly(who5_1=...),
    "who5_1_six": weekly(who5_1=6),
    "phq2_1_four": weekly(phq2_1=4),
    "extra_phq9_3": weekly(phq9_3=1),
}


@pytest.mark.parametrize("body", WEEKLY_REJECTS.values(), ids=WEEKLY_REJECTS.keys())
def test_weekly_rejected(body):
    with pytest.raises(ValidationError):
        WeeklyIn.model_validate(body)
