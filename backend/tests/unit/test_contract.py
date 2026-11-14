"""Ortak sözleşme testleri: fixture'lar, DTO kuralları, hata zarfı, repository imzaları."""
import inspect
import json
import uuid
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel, ValidationError

from app.core.errors import ApiError, install_error_handling
from app.repositories import errors as repo_errors
from app.repositories.interfaces import IdentityRepository, Repository
from app.repositories.records import AlertCreate, JobRequestData, NotificationEventCreate
from app.repositories.sqlalchemy_identity import SqlAlchemyIdentityRepository
from app.schemas.common import (
    AnalysisModule,
    ContractModel,
    ErrorCode,
    ErrorResponse,
    MeasurementDTO,
    Severity,
)

FIX = Path(__file__).parents[1] / "fixtures/contract"


def load(name: str) -> dict:
    return json.loads((FIX / name).read_text(encoding="utf-8"))


# --- Ortak ölçüm DTO'su --------------------------------------------------------


@pytest.mark.parametrize("name", ["measurement_eye_daily.json", "measurement_physio_timestamp.json"])
def test_measurement_fixtures_round_trip(name):
    raw = load(name)
    dto = MeasurementDTO.model_validate(raw)
    assert dto.model_dump(mode="json") == raw  # number kalır, 'Z' korunur


def _eye(**changes) -> dict:
    return load("measurement_eye_daily.json") | changes


@pytest.mark.parametrize(
    ("changes", "why"),
    [
        ({"measured_at": "2027-03-20T09:30:00Z"}, "date hassasiyetinde saat"),
        ({"time_precision": "timestamp"}, "timestamp ama saat yok"),
        ({"time_precision": "timestamp", "measured_at": "2027-03-21T01:00:00Z"}, "tarih uyuşmuyor"),
        ({"time_precision": "timestamp", "measured_at": "2027-03-20T09:30:00"}, "saat dilimi yok"),
        ({"value_text": "x"}, "iki değer birden"),
        ({"value_num": None}, "geçerli ama değer yok"),
        ({"eye": "NA"}, "NA API'de yok"),
        ({"module": "behavioral"}, "göz dışı ölçümde eye dolu"),
        ({"protocol_version": ""}, "protocol_version boş"),
        ({"quality_score": 1.5}, "kalite 0-1 dışı"),
        ({"metadata_json": "{}"}, "metadata metin olamaz"),
        ({"source": "seed"}, "seed DTO'da synthetic olmalı"),
        ({"extra": 1}, "bilinmeyen alan"),
    ],
)
def test_measurement_rules(changes, why):
    with pytest.raises(ValidationError):
        MeasurementDTO.model_validate(_eye(**changes))


def test_invalid_measurement_may_have_no_value():
    dto = MeasurementDTO.model_validate(_eye(valid=False, value_num=None))
    assert dto.value_num is None  # eksik değer 0'a çevrilmez


def test_timestamp_offset_is_normalized_to_utc():
    dto = MeasurementDTO.model_validate(
        _eye(time_precision="timestamp", measured_at="2027-03-20T12:30:00+03:00")
    )
    assert dto.model_dump(mode="json")["measured_at"] == "2027-03-20T09:30:00Z"


# --- Hata zarfı -----------------------------------------------------------------


@pytest.mark.parametrize("name", ["error_idempotency_conflict.json", "error_validation.json"])
def test_error_fixtures(name):
    ErrorResponse.model_validate(load(name))


class _Body(ContractModel):
    eye: str


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    install_error_handling(app)

    @app.post("/echo")
    def echo(body: _Body):
        return body

    @app.get("/conflict")
    def conflict():
        raise repo_errors.IdempotencyConflict("ham ayrıntı yanıta sızmamalı")

    @app.get("/forbidden")
    def forbidden():
        raise ApiError(403, ErrorCode.FORBIDDEN)

    @app.get("/boom")
    def boom():
        raise RuntimeError("SELECT * FROM core.Users -- gizli")

    return TestClient(app, raise_server_exceptions=False)


def _detail(resp) -> dict:
    body = ErrorResponse.model_validate(resp.json())
    assert resp.headers["X-Trace-Id"] == str(body.detail.trace_id)
    return body.detail.model_dump(mode="json")


def test_validation_error_envelope(client):
    resp = client.post("/echo", json={"eye": "OD", "typo": 1})
    assert resp.status_code == 422
    d = _detail(resp)
    assert d["code"] == "VALIDATION_ERROR"
    assert {"field": "typo", "code": "UNKNOWN_FIELD"}.items() <= d["fields"][0].items()


def test_repository_error_mapped(client):
    resp = client.get("/conflict")
    assert resp.status_code == 409
    d = _detail(resp)
    assert d["code"] == "IDEMPOTENCY_CONFLICT"
    assert "ham ayrıntı" not in resp.text


def test_api_error_and_404(client):
    assert _detail(client.get("/forbidden"))["code"] == "FORBIDDEN"
    resp = client.get("/yok")
    assert resp.status_code == 404 and _detail(resp)["code"] == "NOT_FOUND"


def test_unexpected_error_hides_details(client):
    resp = client.get("/boom")
    assert resp.status_code == 500
    assert _detail(resp)["code"] == "INTERNAL_ERROR"
    assert "SELECT" not in resp.text


def test_success_has_no_envelope_but_has_trace(client):
    resp = client.post("/echo", json={"eye": "OD"})
    assert resp.json() == {"eye": "OD"}
    uuid.UUID(resp.headers["X-Trace-Id"])


# --- Repository sözleşmesi -------------------------------------------------------


def _public_methods(cls) -> dict:
    return {
        n: inspect.signature(f)
        for n, f in inspect.getmembers(cls, inspect.isfunction)
        if not n.startswith("_")
    }


def test_identity_repository_matches_protocol():
    proto = _public_methods(IdentityRepository)
    impl = _public_methods(SqlAlchemyIdentityRepository)
    for name, sig in proto.items():
        assert name in impl, name
        assert list(impl[name].parameters) == list(sig.parameters), name


def test_repository_contract_function_names():
    expected = {
        "get_user_by_email", "get_user_by_id", "get_astronaut", "get_measurements",
        "get_sans_context", "create_or_get_job", "get_job", "claim_next_job",
        "renew_job_lease", "recover_expired_jobs", "save_input_snapshot",
        "save_anomaly_result", "save_sans_analysis", "update_sans_state", "finalize_job",
        "create_alert", "create_notification_event", "acknowledge_alert", "resolve_alert",
        "record_receipt",
    }
    extras = {"request_retry", "list_alerts", "list_pending_events", "mark_event_sent"}
    assert set(_public_methods(Repository)) == expected | extras


def test_records_are_frozen_and_strict():
    req = JobRequestData(module=AnalysisModule.SANS, session_id="S-A007-D074")
    with pytest.raises(ValidationError):
        req.session_id = "x"
    with pytest.raises(ValidationError):
        JobRequestData(module=AnalysisModule.ANOMALY, module_scope="combined", session_id="S")
    with pytest.raises(ValidationError):
        AlertCreate(astronaut_id="A007", module="sans", severity=Severity.NORMAL, sans_analysis_id=1)
    with pytest.raises(ValidationError):
        NotificationEventCreate(
            event_type="analysis.completed", audience="GROUND_CONTROL",
            target_user_id=None, job_id=uuid.uuid4(), payload={},
        )
    assert issubclass(type(req), BaseModel)
