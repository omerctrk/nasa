"""A7 kabul (DB'siz): giriş kuralları, yetki, hata kodları."""
import datetime as dt
import uuid

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.db.session import get_db
from app.main import app
from app.routers.deps import require_active_astronaut
from app.schemas.behavioral import CheckinIn, CognitiveIn, sleep_hours_between
from app.schemas.common import CurrentUser
from app.services.data_entry import etag_of

ASTRO = CurrentUser(user_id=uuid.uuid4(), role="ASTRONAUT", astronaut_id="A007")

CHECKIN = dict(mood=6, energy=5, stress=4, loneliness=1, crew=3, mood_index=60,
               bed_time="23:30:00", wake_time="07:00:00", sleep_quality=4)



def test_sleep_hours_across_midnight():
    assert sleep_hours_between(dt.time(23, 30), dt.time(7, 0)) == 7.5
    assert sleep_hours_between(dt.time(1, 0), dt.time(6, 30)) == 5.5


def test_etag_is_stable_and_ms_precise():
    t = dt.datetime(2027, 3, 20, 9, 30, 0, 123000)
    assert etag_of(t) == etag_of(t.replace(tzinfo=dt.UTC)) != etag_of(t.replace(microsecond=124000))


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


@pytest.fixture
def client():
    app.dependency_overrides[get_db] = lambda: None
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


def test_without_login_is_401(client):
    r = client.put("/api/v1/me/checkins/2027-03-20", json=CHECKIN)
    assert r.status_code == 401 and r.json()["detail"]["code"] == "UNAUTHORIZED"


def test_every_entry_route_requires_active_astronaut():
    """Rol/aktiflik/gösterim kontrolü Ö1'in require_active_astronaut'unda (Ömer'in testleri);
    burada her veri giriş ucunun bu dependency'ye bağlı olduğunu doğruluyoruz."""
    from app.routers import entries

    for route in entries.router.routes:
        deps = {d.call for d in route.dependant.dependencies}
        assert require_active_astronaut in deps, route.path


def test_validation_uses_shared_envelope(client):
    app.dependency_overrides[require_active_astronaut] = lambda: ASTRO
    r = client.put("/api/v1/me/checkins/2027-03-20", json=CHECKIN | {"mood": 11, "astronaut_id": "X"})
    d = r.json()["detail"]
    assert r.status_code == 422 and d["code"] == "VALIDATION_ERROR"
    assert {f["field"] for f in d["fields"]} == {"mood", "astronaut_id"}  # astronaut_id istemciden alınmaz
