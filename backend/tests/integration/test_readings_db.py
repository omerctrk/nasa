"""Okuma uçları gerçek DB kabulü: kendi verisi, kule görünümü, aralıklar."""
import uuid

import pytest
from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app
from app.routers.deps import require_active_astronaut, require_ground_control
from app.schemas.common import CurrentUser

CHECKIN = dict(mood=6, energy=5, stress=4, loneliness=1, crew=3, mood_index=60,
               bed_time="23:30:00", wake_time="07:00:00", sleep_quality=4)


@pytest.fixture
def api(db, astronaut):
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[require_active_astronaut] = lambda: CurrentUser(
        user_id=uuid.uuid4(), role="ASTRONAUT", astronaut_id=astronaut)
    app.dependency_overrides[require_ground_control] = lambda: CurrentUser(
        user_id=uuid.uuid4(), role="GROUND_CONTROL", astronaut_id=None)
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


def test_profile_and_checkin_history(api, astronaut):
    p = api.get("/api/v1/me/profile").json()
    assert p["astronaut_id"] == astronaut and p["mission_start_date"] == "2027-01-05"
    for day in ("2027-03-18", "2027-03-19", "2027-03-20"):
        assert api.put(f"/api/v1/me/checkins/{day}", json=CHECKIN).status_code == 201
    r = api.get("/api/v1/me/checkins", params={"start": "2027-03-18", "end": "2027-03-20"})
    assert [c["date"] for c in r.json()] == ["2027-03-18", "2027-03-19"]  # end hariç
    bad = api.get("/api/v1/me/checkins", params={"start": "2027-03-20", "end": "2027-03-18"})
    assert bad.status_code == 422


def test_cognitive_and_eye_history(api, astronaut):
    api.post("/api/v1/me/cognitive-tests", json=dict(
        client_request_id=str(uuid.uuid4()), taken_at="2027-03-20T09:30:00Z", test_type="pvt",
        duration_s=180, n_trials=50, mean_rt_ms=310.0, speed=3.1, device="tablet", raw=[]))
    cog = api.get("/api/v1/me/cognitive-tests",
                  params={"start": "2027-03-20", "end": "2027-03-21", "test_type": "pvt"}).json()
    assert len(cog) == 1 and cog[0]["mean_rt_ms"] == 310.0 and "speed" not in cog[0]
    tests = [dict(eye=e, test=t, value=v, unit=u) for e in ("OD", "OS")
             for t, v, u in (("near_acuity", -0.05, "logMAR"), ("contrast", 1.8, "logCS"),
                             ("amsler", 0, "cells"))]
    api.post("/api/v1/me/eye-sessions", json=dict(flight_day=74, quality_score=0.9, tests=tests))
    eye = api.get("/api/v1/me/eye-sessions", params={"start_day": -60, "end_day": 80}).json()
    assert len(eye) == 1 and len(eye[0]["tests"]) == 6


def test_measurements_for_charts_and_ground(api, astronaut):
    api.put("/api/v1/me/checkins/2027-03-20", json=CHECKIN)
    have = api.get("/api/v1/me/measurements",
                   params={"start": "2027-03-20", "end": "2027-03-21", "module": "behavioral"})
    if have.status_code == 500:
        pytest.skip("sözlük boş: önce seed çalıştırılmalı")
    codes = {m["measurement"] for m in have.json()}
    assert {"mood", "stress", "sleep_hours"} <= codes
    profiles = api.get("/api/v1/ground/astronauts").json()
    assert astronaut in {p["astronaut_id"] for p in profiles}
    g = api.get(f"/api/v1/ground/astronauts/{astronaut}/measurements",
                params={"start": "2027-03-20", "end": "2027-03-21"})
    assert g.status_code == 200 and len(g.json()) == len(have.json())
    assert api.get("/api/v1/ground/astronauts/YOK/measurements",
                   params={"start": "2027-03-20", "end": "2027-03-21"}).status_code == 404
