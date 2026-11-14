"""A7 gerçek DB kabulü: uçtan uca HTTP → servis → MS SQL (her test rollback)."""
import uuid

import pytest
from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app
from app.models import Astronaut, MeasurementDefinition
from app.routers.deps import require_active_astronaut
from app.schemas.common import CurrentUser

CHECKIN = dict(mood=6, energy=5, stress=4, loneliness=1, crew=3, mood_index=60,
               bed_time="23:30:00", wake_time="07:00:00", sleep_quality=4)


def eye_tests(near=-0.05):
    return [dict(eye=e, test=t, value=v, unit=u) for e in ("OD", "OS")
            for t, v, u in (("near_acuity", near, "logMAR"), ("contrast", 1.8, "logCS"),
                            ("amsler", 0, "cells"))]


@pytest.fixture
def api(db, astronaut):
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[require_active_astronaut] = lambda: CurrentUser(
        user_id=uuid.uuid4(), role="ASTRONAUT", astronaut_id=astronaut)
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


def code(r):
    return r.json()["detail"]["code"]


def test_checkin_put_with_etag(api):
    url = "/api/v1/me/checkins/2027-03-20"
    r = api.put(url, json=CHECKIN)
    assert r.status_code == 201 and r.json()["mission_day"] == 74
    assert r.json()["sleep_hours"] == 7.5 and r.json()["source"] == "manual"
    etag = r.headers["ETag"]
    assert api.put(url, json=CHECKIN).status_code == 412  # If-Match yok
    r2 = api.put(url, json=CHECKIN | {"mood": 3}, headers={"If-Match": etag})
    assert r2.status_code == 200 and r2.json()["mood"] == 3
    assert api.put(url, json=CHECKIN, headers={"If-Match": etag}).status_code == 412  # eski
    g = api.get(url)
    assert g.json()["mood"] == 3 and g.headers["ETag"] == r2.headers["ETag"]
    assert api.get("/api/v1/me/checkins/2027-03-21").status_code == 404


def test_weekly_idempotency(api):
    body = dict(client_request_id=str(uuid.uuid4()), taken_at="2027-03-20T10:00:00Z",
                answers={"who5": [3, 3, 3, 3, 3]}, who5_score=60, phq2_score=1, gad2_score=2)
    a = api.post("/api/v1/me/weekly-assessments", json=body)
    b = api.post("/api/v1/me/weekly-assessments", json=body)
    assert (a.status_code, b.status_code) == (201, 200) and a.json()["id"] == b.json()["id"]
    c = api.post("/api/v1/me/weekly-assessments", json=body | {"phq2_score": 5})
    assert c.status_code == 409 and code(c) == "IDEMPOTENCY_CONFLICT"


def test_cognitive(api):
    body = dict(client_request_id=str(uuid.uuid4()), taken_at="2027-03-20T12:30:00+03:00",
                test_type="pvt", duration_s=180, n_trials=50, mean_rt_ms=310.5, lapses=2,
                device="tablet", raw=[{"rt": 300}])
    r = api.post("/api/v1/me/cognitive-tests", json=body)
    assert r.status_code == 201 and r.json()["mission_day"] == 74
    assert r.json()["taken_at"].startswith("2027-03-20T09:30:00")  # UTC'ye çevrildi
    assert api.post("/api/v1/me/cognitive-tests", json=body).status_code == 200


def test_physiological(api, db):
    hr = f"hr_{uuid.uuid4().hex[:6]}"
    db.add(MeasurementDefinition(measurement_code=hr,
                                 module="physiological", canonical_unit="bpm",
                                 value_kind="numeric", protocol_version="test",
                                 worsening_direction="unconfirmed"))
    db.flush()
    body = dict(client_request_id=str(uuid.uuid4()), measurement=hr, value_num=64, unit="bpm",
                measured_date="2027-03-20")
    assert code(api.post("/api/v1/me/physiological", json=body | {"measurement": "mood"})) \
        == "VALIDATION_ERROR"  # davranış kodu fizyolojik değil
    assert code(api.post("/api/v1/me/physiological", json=body | {"unit": "x"})) \
        == "VALIDATION_ERROR"
    r = api.post("/api/v1/me/physiological", json=body)
    assert r.status_code == 201 and r.json()["mission_day"] == 74
    assert api.post("/api/v1/me/physiological", json=body).status_code == 200
    assert api.post("/api/v1/me/physiological", json=body | {"value_num": 70}).status_code == 409


def test_eye_session_and_retest(api, astronaut):
    base = dict(flight_day=74, quality_score=0.92, checklist={"distance_ok": True},
                tests=eye_tests())
    r = api.post("/api/v1/me/eye-sessions", json=base)
    sid = f"S-{astronaut}-D074"
    assert r.status_code == 201 and r.json()["session_id"] == sid
    assert r.json()["test_count"] == 6
    assert api.post("/api/v1/me/eye-sessions", json=base).status_code == 200
    assert api.post("/api/v1/me/eye-sessions",
                    json=base | {"tests": eye_tests(near=0.1)}).status_code == 409
    rt = api.post("/api/v1/me/eye-sessions", json=dict(base, flight_day=75, retest_of=sid))
    assert rt.status_code == 201 and rt.json()["is_retest"] is True
    bad = api.post("/api/v1/me/eye-sessions", json=dict(base, flight_day=76, retest_of="S-YOK"))
    assert bad.status_code == 422
    pre = api.post("/api/v1/me/eye-sessions", json=dict(base, flight_day=-60))
    assert pre.json()["session_id"] == f"S-{astronaut}-M060"


def test_headache_single_source(api):
    url = "/api/v1/me/symptoms/headache"
    assert api.post(url, json={"flight_day": 74, "headache": True}).status_code == 201
    assert api.post(url, json={"flight_day": 74, "headache": True}).status_code == 200
    assert api.post(url, json={"flight_day": 74, "headache": False}).status_code == 409
    r = api.put("/api/v1/me/checkins/2027-03-22", json=CHECKIN | {"symptoms": ["headache"]})
    assert r.status_code == 422


def test_display_profile_cannot_write(api, db, astronaut):
    other = Astronaut(astronaut_id=f"D{uuid.uuid4().hex[:8]}", display_name="Gösterim",
                      mission_id=db.get(Astronaut, astronaut).mission_id, is_display_only=True)
    db.add(other)
    db.flush()
    app.dependency_overrides[require_active_astronaut] = lambda: CurrentUser(
        user_id=uuid.uuid4(), role="ASTRONAUT", astronaut_id=other.astronaut_id)
    r = api.post("/api/v1/me/symptoms/headache", json={"flight_day": 74, "headache": True})
    assert r.status_code == 403 and code(r) == "FORBIDDEN"
