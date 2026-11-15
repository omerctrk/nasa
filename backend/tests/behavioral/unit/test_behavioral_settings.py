"""Demo saati ayarı (BEHAVIORAL_FIXED_NOW), test günü kuralı ve geçici kimlik bağımlılığı."""
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.api.behavioral_errors_http import register_behavioral_error_handlers, validation_fields
from app.api.deps_behavioral import get_current_astronaut_id
from app.core.behavioral_settings import FIXED_NOW_ENV, TEST_WEEKDAYS, utc_now
from app.services.behavioral_calendar import consecutive_missing, is_test_day
from app.services.behavioral_errors import BehavioralError


def test_utc_now_uses_fixed_env(monkeypatch):
    monkeypatch.setenv(FIXED_NOW_ENV, "2026-11-14T09:00:00Z")
    assert utc_now() == datetime(2026, 11, 14, 9, 0, tzinfo=timezone.utc)


def test_utc_now_converts_offset_to_utc(monkeypatch):
    monkeypatch.setenv(FIXED_NOW_ENV, "2026-11-14T12:00:00+03:00")
    value = utc_now()
    assert value == datetime(2026, 11, 14, 9, 0, tzinfo=timezone.utc) and value.utcoffset() == timedelta(0)


def test_utc_now_rejects_naive_env(monkeypatch):
    monkeypatch.setenv(FIXED_NOW_ENV, "2026-11-14T09:00:00")
    with pytest.raises(ValueError):
        utc_now()


def test_utc_now_real_clock_without_env(monkeypatch):
    monkeypatch.delenv(FIXED_NOW_ENV, raising=False)
    value = utc_now()
    assert value.tzinfo is not None and abs(datetime.now(timezone.utc) - value) < timedelta(seconds=5)


@pytest.fixture(scope="module")
def whoami():
    app = FastAPI()
    register_behavioral_error_handlers(app)

    @app.get("/api/v1/behavioral/whoami")
    def whoami_route(astronaut_id: str = Depends(get_current_astronaut_id)):
        return {"astronaut_id": astronaut_id}

    client = TestClient(app)
    return lambda header: client.get("/api/v1/behavioral/whoami",
                                     headers={} if header is None else {"Authorization": header})


# HTTPBearer şema adını büyük/küçük harf duyarsız okur (RFC 7235): "bearer A007" de kabul.
@pytest.mark.parametrize("header,expected", [("Bearer A007", "A007"), ("Bearer A123", "A123"),
                                             ("bearer A007", "A007")])
def test_bearer_token_is_astronaut_id(whoami, header, expected):
    resp = whoami(header)
    assert resp.status_code == 200 and resp.json() == {"astronaut_id": expected}


@pytest.mark.parametrize("header", [None, "", "Bearer", "Bearer A07", "Bearer A0071", "Token A007",
                                    "Basic A007", "Bearer A007 extra"])
def test_bad_bearer_token_unauthorized(whoami, header):
    resp = whoami(header)
    assert resp.status_code == 401 and resp.headers["WWW-Authenticate"] == "Bearer"
    assert resp.json()["detail"]["code"] == "unauthorized"


def test_get_current_astronaut_id_without_credentials_raises():
    with pytest.raises(BehavioralError) as excinfo:
        get_current_astronaut_id(None)
    assert (excinfo.value.code, excinfo.value.status) == ("unauthorized", 401)


# ---------------------------------------------------------------- takvim

def test_test_weekdays_match_seed_rule():
    from scripts.seed_behavioral import CONFIG
    assert TEST_WEEKDAYS == set(CONFIG["test_weekdays"])


@pytest.mark.parametrize("d,expected", [
    (date(2026, 9, 1), True), (date(2026, 9, 4), True), (date(2026, 9, 2), False),
    (date(2026, 11, 10), True), (date(2026, 11, 13), True), (date(2026, 11, 14), False),
    (date(2026, 8, 28), False),
])
def test_is_test_day(d, expected):
    assert is_test_day(d, date(2026, 9, 1)) is expected


def test_seed_test_days_match_calendar_rule():
    from scripts.seed_behavioral import generate
    start = date(2026, 9, 1)
    seed_days = {date.fromisoformat(r["taken_at"][:10]) for r in generate()["cognitive_tests"]}
    rule_days = {start + timedelta(days=k) for k in range(74) if is_test_day(start + timedelta(days=k), start)}
    assert seed_days == rule_days


def test_consecutive_missing_stops_at_mission_start():
    start = date(2026, 9, 1)
    assert consecutive_missing(set(), date(2026, 9, 1), start) == 1
    assert consecutive_missing({date(2026, 9, 1)}, date(2026, 9, 3), start) == 2
    assert consecutive_missing({date(2026, 9, 3)}, date(2026, 9, 3), start) == 0


@pytest.mark.parametrize("loc,expected", [
    (("body", "mood"), "mood"),
    (("path", "date"), "date"),
    (("body", "pvt", "trials", 3, "rt_ms"), "rt_ms"),
    (("body", "answers", "who5_1"), "who5_1"),
    (("body",), "body"),
])
def test_validation_field_names(loc, expected):
    assert validation_fields([{"loc": loc, "type": "x"}]) == [expected]
