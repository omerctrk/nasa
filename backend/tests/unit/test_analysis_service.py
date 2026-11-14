from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from copy import deepcopy
from uuid import UUID, uuid4

import pytest

from app.core.errors import ApiError
from app.repositories.errors import IdempotencyConflict, InvalidStateTransition, NotFound
from app.repositories.records import JobRequestData
from app.repositories.interfaces import JobApiRepository
from app.schemas.analysis import AnomalyJobRequest, SansJobRequest
from app.schemas.common import CurrentUser, EvaluationStatus, JobState
from app.services.analysis import AnalysisService, canonical_request_hash
from tests.fakes.analysis import FakeJobStore


@pytest.fixture
def setup():
    store = FakeJobStore()
    return store, AnalysisService(store.transaction), CurrentUser(
        user_id=UUID(int=1), role="ASTRONAUT", astronaut_id="A007")


def request(key=None, scope="combined"):
    return AnomalyJobRequest(module="anomaly", idempotency_key=key or uuid4(), module_scope=scope)


def test_canonical_hash_uses_only_normalized_request_fields():
    first = SansJobRequest(module="sans", idempotency_key=uuid4(), session_id=" S-A007-D074 ")
    second = SansJobRequest(module="sans", idempotency_key=uuid4(), session_id="S-A007-D074")
    assert canonical_request_hash(first.to_record()) == canonical_request_hash(second.to_record())
    assert canonical_request_hash(request().to_record()) == canonical_request_hash(request().to_record())
    assert canonical_request_hash(request(scope="combined").to_record()) != canonical_request_hash(
        request(scope="physiological").to_record())
    assert len(canonical_request_hash(first.to_record())) == 64


def test_create_repeat_conflict_and_status(setup):
    store, service, user = setup
    body = request()
    first = service.create(user, body)
    assert first.created and store.commits == 1
    repeat = service.create(user, body)
    assert not repeat.created and repeat.response == first.response
    with pytest.raises(IdempotencyConflict):
        service.create(user, request(body.idempotency_key, "physiological"))
    status = service.get(user, first.response.job_id)
    assert status.state == JobState.QUEUED
    assert status.evaluation_status is None
    assert status.anomaly_result_id is None and status.sans_analysis_id is None
    assert len(store.jobs) == 1
    with store.transaction() as repo:
        assert isinstance(repo, JobApiRepository)


def test_key_scope_is_per_astronaut_and_cross_module_conflicts(setup):
    store, service, user = setup
    body = request()
    first = service.create(user, body)
    other = CurrentUser(user_id=UUID(int=2), role="ASTRONAUT", astronaut_id="A009")
    second = service.create(other, body)
    assert first.response.job_id != second.response.job_id
    with pytest.raises(IdempotencyConflict):
        service.create(user, SansJobRequest(module="sans", idempotency_key=body.idempotency_key,
                                            session_id="S-A007-D074"))


def test_scope_errors_and_missing_records(setup):
    _, service, user = setup
    job = service.create(user, request()).response
    other = CurrentUser(user_id=UUID(int=2), role="ASTRONAUT", astronaut_id="A009")
    for identity, job_id in [(other, job.job_id), (user, uuid4())]:
        with pytest.raises(NotFound):
            service.get(identity, job_id)
        with pytest.raises(NotFound):
            service.retry(identity, job_id)
    ground = CurrentUser(user_id=UUID(int=3), role="GROUND_CONTROL", astronaut_id=None)
    with pytest.raises(ApiError) as caught:
        service.create(ground, request())
    assert caught.value.status_code == 403


def test_retry_preserves_snapshot_and_request(setup):
    store, service, user = setup
    job = service.create(user, request()).response
    snapshot = {"records": [{"record_id": "test:1", "value_num": 42}], "threshold_version": "test-v1"}
    store.mark_failed(job.job_id, snapshot, "f" * 64)
    before = deepcopy(store.jobs[job.job_id])
    result = service.retry(user, job.job_id)
    after = store.jobs[job.job_id]
    assert result.job_id == job.job_id and result.state == JobState.QUEUED
    assert after.record.attempts == 0 and after.record.retry_cycle == 1
    assert after.record.request == before.record.request
    assert (after.snapshot, after.input_hash) == (before.snapshot, before.input_hash)
    assert after.record.error_code is None and after.record.has_snapshot
    with pytest.raises(InvalidStateTransition):
        service.retry(user, job.job_id)


def test_retry_before_snapshot_exists(setup):
    store, service, user = setup
    job = service.create(user, request()).response
    store.mark_failed(job.job_id)
    service.retry(user, job.job_id)
    assert store.jobs[job.job_id].snapshot is None
    assert store.jobs[job.job_id].input_hash is None
    assert not store.jobs[job.job_id].record.has_snapshot


@pytest.mark.parametrize("state", ["QUEUED", "SYNCING", "ANALYZING", "COMPLETED"])
def test_retry_rejects_non_failed_jobs(setup, state):
    store, service, user = setup
    job = service.create(user, request()).response
    store.jobs[job.job_id].record = store.jobs[job.job_id].record.model_copy(update={"state": JobState(state)})
    with pytest.raises(InvalidStateTransition):
        service.retry(user, job.job_id)


def test_commit_failure_rolls_back_create_and_retry(setup):
    store, service, user = setup
    store.fail_next_commit = True
    body = request()
    with pytest.raises(RuntimeError):
        service.create(user, body)
    assert not store.jobs and not store.keys
    job = service.create(user, body).response
    store.mark_failed(job.job_id, {"value": "frozen"}, "f" * 64)
    before = deepcopy(store.jobs[job.job_id])
    store.fail_next_commit = True
    with pytest.raises(RuntimeError):
        service.retry(user, job.job_id)
    assert store.jobs[job.job_id] == before


@pytest.mark.parametrize("evaluation", ["insufficient_data", "invalid_data"])
def test_unevaluated_completion_keeps_result_null(setup, evaluation):
    store, service, user = setup
    job = service.create(user, request()).response
    stored = store.jobs[job.job_id]
    stored.record = stored.record.model_copy(update={"state": JobState.COMPLETED,
                                                      "evaluation_status": EvaluationStatus(evaluation)})
    status = service.get(user, job.job_id)
    assert status.state == JobState.COMPLETED
    assert status.evaluation_status == evaluation
    assert status.anomaly_result_id is None and status.sans_analysis_id is None


def test_status_serializes_database_utc_time_and_rejects_raw_errors(setup):
    store, service, user = setup
    job = service.create(user, request()).response
    stored = store.jobs[job.job_id]
    stored.record = stored.record.model_copy(update={
        "created_at": stored.record.created_at.replace(tzinfo=None),
        "updated_at": stored.record.updated_at.replace(tzinfo=None),
    })
    status = service.get(user, job.job_id)
    assert status.model_dump(mode="json")["created_at"].endswith("Z")
    stored.record = stored.record.model_copy(update={"error_code": "SELECT secret FROM table"})
    with pytest.raises(ValueError):
        service.get(user, job.job_id)


def test_concurrent_same_key_and_retry(setup):
    store, service, user = setup
    body = request()
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: service.create(user, body), range(12)))
    assert sum(result.created for result in results) == 1
    assert len({result.response.job_id for result in results}) == 1
    job_id = results[0].response.job_id
    store.mark_failed(job_id)

    def retry(_):
        try:
            service.retry(user, job_id)
            return "accepted"
        except InvalidStateTransition:
            return "conflict"

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(retry, range(8)))
    assert results.count("accepted") == 1
    assert store.jobs[job_id].record.retry_cycle == 1
