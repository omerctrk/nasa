from contextlib import contextmanager
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.analysis_runtime import configure_analysis
from app.core.errors import install_error_handling
from app.core.security import AuthSettings, TokenCodec
from app.routers.auth import install_auth
from app.services.analysis import AnalysisService
from tests.fakes.analysis import FakeJobStore
from tests.fakes.auth import FakeAuthRepository
from tests.fixtures.auth import make_auth_repository


@pytest.fixture
def api():
    auth = make_auth_repository()
    users = [auth.get_user_by_id(UUID(int=n)) for n in range(1, 7)]
    users.append(users[0].model_copy(update={"user_id": UUID(int=7), "email": "other@example.test",
                                            "astronaut_id": "A009"}))
    profiles = [auth.get_astronaut("A007"), auth.get_astronaut("A008")]
    profiles.append(profiles[0].model_copy(update={"astronaut_id": "A009"}))

    @contextmanager
    def auth_factory():
        yield FakeAuthRepository(users, profiles)

    settings = AuthSettings(jwt_secret="test-only-" + "x" * 48)
    app = FastAPI()
    install_error_handling(app)
    install_auth(app, auth_factory, settings)
    configure_analysis(app)
    store = FakeJobStore()
    app.state.analysis_service = AnalysisService(store.transaction)  # explicit TEST injection only
    tokens = TokenCodec(settings)

    def headers(number=1):
        return {"Authorization": f"Bearer {tokens.issue(UUID(int=number))}"}

    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, store, headers, app


def body(**changes):
    return {"module": "anomaly", "idempotency_key": str(uuid4()), "module_scope": "combined"} | changes


def create(api, payload=None):
    client, _, headers, _ = api
    response = client.post("/api/v1/analysis/jobs", json=payload or body(), headers=headers())
    assert response.status_code == 202, response.text
    return response


def test_new_job_repeat_and_status(api):
    client, store, headers, _ = api
    payload = body()
    response = create(api, payload)
    accepted = response.json()
    assert set(accepted) == {"job_id", "module", "state", "status_url"}
    assert accepted["state"] == "QUEUED"
    assert response.headers["location"] == accepted["status_url"]
    assert response.headers["cache-control"] == "no-store"
    repeat = client.post("/api/v1/analysis/jobs", json=payload, headers=headers())
    assert repeat.status_code == 200 and repeat.json() == accepted
    status = client.get(accepted["status_url"], headers=headers())
    assert status.status_code == 200
    assert status.json()["evaluation_status"] is None
    assert status.json()["anomaly_result_id"] is None
    assert status.json()["sans_analysis_id"] is None
    for internal in ["request_hash", "input_snapshot_json", "provider_metadata_json", "lease_token", "has_snapshot"]:
        assert internal not in status.json()
    assert len(store.jobs) == 1


def test_key_conflict(api):
    client, _, headers, _ = api
    payload = body()
    create(api, payload)
    conflict = client.post("/api/v1/analysis/jobs", json=payload | {"module_scope": "behavioral"},
                           headers=headers())
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "IDEMPOTENCY_CONFLICT"


@pytest.mark.parametrize("payload", [
    {"module": "sans", "idempotency_key": str(uuid4()), "session_id": "S-A007-D074"},
    body(module_scope="sans"),
])
def test_sans_is_closed(api, payload):
    """SANS/göz modülü projeden çıkarıldı (takım kararı): API SANS işi ve SANS kapsamı almaz."""
    client, store, headers, _ = api
    response = client.post("/api/v1/analysis/jobs", json=payload, headers=headers())
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "VALIDATION_ERROR"
    assert not store.jobs


@pytest.mark.parametrize("payload", [
    body(session_id="S-A007-D074"), body(astronaut_id="A009"), body(user_id=str(uuid4())),
    body(module="unknown"), body(module_scope="unknown"), body(idempotency_key="bad"),
    {"module": "anomaly", "idempotency_key": str(uuid4())},
    {"module": "sans", "idempotency_key": str(uuid4()), "session_id": "   "},
    {"module": "sans", "idempotency_key": str(uuid4()), "session_id": "x" * 65},
    {"module": "sans", "idempotency_key": str(uuid4()), "session_id": 123},
    {"module": "sans", "idempotency_key": str(uuid4()), "session_id": "S", "module_scope": "sans"},
])
def test_invalid_requests_are_rejected_without_job(api, payload):
    client, store, headers, _ = api
    response = client.post("/api/v1/analysis/jobs", json=payload, headers=headers())
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "VALIDATION_ERROR"
    assert not store.jobs


def test_auth_roles_and_scoped_reads(api):
    client, _, headers, _ = api
    assert client.post("/api/v1/analysis/jobs", json=body()).status_code == 401
    for number in [2, 3, 4]:  # ground, inactive, display
        assert client.post("/api/v1/analysis/jobs", json=body(), headers=headers(number)).status_code == 403
    accepted = create(api).json()
    for suffix in ["", "/retry"]:
        method = client.get if not suffix else client.post
        response = method(accepted["status_url"] + suffix, headers=headers(7))
        assert response.status_code == 404
        assert response.json()["detail"]["code"] == "NOT_FOUND"
    assert client.get(f"/api/v1/analysis/jobs/{uuid4()}", headers=headers()).status_code == 404
    assert client.get("/api/v1/analysis/jobs/invalid-uuid", headers=headers()).status_code == 422


def test_retry_preserves_frozen_inputs_and_rejects_new_data(api):
    client, store, headers, _ = api
    accepted = create(api).json()
    job_id = UUID(accepted["job_id"])
    store.mark_failed(job_id, {"sentinel": "PRIVATE-SNAPSHOT"}, "a" * 64)
    for replacement in [{"snapshot": {}}, {"module_scope": "physiological"}, {"idempotency_key": str(uuid4())}]:
        assert client.post(accepted["status_url"] + "/retry", json=replacement, headers=headers()).status_code == 422
    response = client.post(accepted["status_url"] + "/retry", headers=headers())
    assert response.status_code == 202
    assert response.json()["job_id"] == accepted["job_id"]
    assert response.json()["state"] == "QUEUED"
    assert store.jobs[job_id].snapshot == {"sentinel": "PRIVATE-SNAPSHOT"}
    assert store.jobs[job_id].input_hash == "a" * 64
    status = client.get(accepted["status_url"], headers=headers())
    assert status.json()["retry_cycle"] == 1 and status.json()["attempts"] == 0
    assert "PRIVATE-SNAPSHOT" not in status.text
    duplicate = client.post(accepted["status_url"] + "/retry", json={}, headers=headers())
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["code"] == "INVALID_STATE_TRANSITION"


def test_repeating_original_request_after_failure_does_not_retry(api):
    client, store, headers, _ = api
    payload = body()
    accepted = create(api, payload).json()
    store.mark_failed(UUID(accepted["job_id"]))
    repeat = client.post("/api/v1/analysis/jobs", json=payload, headers=headers())
    assert repeat.status_code == 200
    assert repeat.json()["state"] == "FAILED"
    assert store.jobs[UUID(accepted["job_id"])].record.retry_cycle == 0


def test_commit_failure_returns_error_and_does_not_accept_job(api):
    client, store, headers, _ = api
    payload = body()
    store.fail_next_commit = True
    response = client.post("/api/v1/analysis/jobs", json=payload, headers=headers())
    assert response.status_code == 500 and not store.jobs
    assert "test commit failure" not in response.text
    assert create(api, payload).status_code == 202


def test_missing_a3_returns_service_unavailable_not_fake_success(api):
    client, store, headers, app = api
    configure_analysis_service = app.state.analysis_service
    app.state.analysis_service = None
    response = client.post("/api/v1/analysis/jobs", json=body(), headers=headers())
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "SERVICE_UNAVAILABLE"
    assert not store.jobs
    app.state.analysis_service = configure_analysis_service


def test_openapi_describes_request_and_replay_response(api):
    client, _, _, _ = api
    paths = client.get("/openapi.json").json()["paths"]
    create_spec = paths["/api/v1/analysis/jobs"]["post"]
    schema = create_spec["requestBody"]["content"]["application/json"]["schema"]
    assert schema["$ref"].endswith("/AnomalyJobRequest")  # SANS kapalı: tek istek türü
    assert {"200", "202"} <= set(create_spec["responses"])
    assert "/api/v1/analysis/jobs/{job_id}" in paths
    assert "/api/v1/analysis/jobs/{job_id}/retry" in paths
