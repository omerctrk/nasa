"""A7 kabul (DB'siz): giriş kuralları, yetki, hata kodları."""
import datetime as dt
import uuid

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.db.session import get_db
from app.main import app
from app.routers.deps import current_user
from app.schemas.behavioral import CheckinIn, CognitiveIn, sleep_hours_between
from app.schemas.common import CurrentUser
from app.schemas.sans import EyeSessionIn
from app.services.data_entry import etag_of, session_id_for

ASTRO = CurrentUser(user_id=uuid.uuid4(), role="ASTRONAUT", astronaut_id="A007")
GROUND = CurrentUser(user_id=uuid.uuid4(), role="GROUND_CONTROL", astronaut_id=None)

CHECKIN = dict(mood=6, energy=5, stress=4, loneliness=1, crew=3, mood_index=60,
               bed_time="23:30:00", wake_time="07:00:00", sleep_quality=4)


def eye_tests(**override):
    tests = [dict(eye=e, test=t, value=v, unit=u)
             for e in ("OD", "OS")
             for t, v, u in (("near_acuity", -0.05, "logMAR"), ("contrast", 1.8, "logCS"),
                             ("amsler", 0, "cells"))]
    tests[0].update(override)
    return tests


def test_sleep_hours_across_midnight():
    assert sleep_hours_between(dt.time(23, 30), dt.time(7, 0)) == 7.5
    assert sleep_hours_between(dt.time(1, 0), dt.time(6, 30)) == 5.5


def test_session_ids():
    assert session_id_for("A007", 74) == "S-A007-D074"
    assert session_id_for("A007", -60) == "S-A007-M060"


def test_etag_is_stable_and_ms_precise():
    t = dt.datetime(2027, 3, 20, 9, 30, 0, 123000)
    assert etag_of(t) == etag_of(t.replace(tzinfo=dt.UTC)) != etag_of(t.replace(microsecond=124000))


def test_headache_must_not_go_into_checkin():
    with pytest.raises(ValidationError, match="Baş ağrısı"):
        CheckinIn(**CHECKIN, symptoms=["nausea", "Headache"])


def test_cognitive_metrics_must_match_test_type():
    base = dict(client_request_id=uuid.uuid4(), taken_at="2027-03-20T09:30:00Z", duration_s=180,
                n_trials=50, device="tablet", raw=[])
    CognitiveIn(**base, test_type="pvt", mean_rt_ms=300, lapses=1)
    with pytest.raises(ValidationError, match="olamaz"):
        CognitiveIn(**base, test_type="pvt", accuracy=0.9)
    with pytest.raises(ValidationError, match="invalid_reason"):
        CognitiveIn(**base, test_type="dsst", accuracy=0.9, valid=False)
    with pytest.raises(ValidationError, match="saat dilimi"):
        CognitiveIn(**(base | {"taken_at": "2027-03-20T09:30:00"}), test_type="pvt")


def test_eye_session_needs_full_six_with_right_units():
    EyeSessionIn(flight_day=74, quality_score=0.9, tests=eye_tests())
    with pytest.raises(ValidationError, match="6 farklı"):
        EyeSessionIn(flight_day=74, quality_score=0.9, tests=eye_tests()[:5])
    with pytest.raises(ValidationError, match="logMAR"):
        EyeSessionIn(flight_day=74, quality_score=0.9, tests=eye_tests(unit="logCS"))


@pytest.fixture
def client():
    app.dependency_overrides[get_db] = lambda: None
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


def test_without_login_is_401(client):
    r = client.put("/api/v1/me/checkins/2027-03-20", json=CHECKIN)
    assert r.status_code == 401 and r.json()["detail"]["code"] == "UNAUTHORIZED"


def test_ground_control_cannot_enter_astronaut_data(client):
    app.dependency_overrides[current_user] = lambda: GROUND
    r = client.post("/api/v1/me/symptoms/headache", json={"flight_day": 74, "headache": True})
    assert r.status_code == 403 and r.json()["detail"]["code"] == "FORBIDDEN"


def test_validation_uses_shared_envelope(client):
    app.dependency_overrides[current_user] = lambda: ASTRO
    r = client.put("/api/v1/me/checkins/2027-03-20", json=CHECKIN | {"mood": 11, "astronaut_id": "X"})
    d = r.json()["detail"]
    assert r.status_code == 422 and d["code"] == "VALIDATION_ERROR"
    assert {f["field"] for f in d["fields"]} == {"mood", "astronaut_id"}  # astronaut_id istemciden alınmaz
