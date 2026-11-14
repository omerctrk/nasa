"""Ö2 acceptance against A3's actual SQL repository (RUN_DB_TESTS=1).

Uses the existing rollback fixture; no schema/seed is created by these tests.
"""

import json
from contextlib import contextmanager
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.core.analysis_runtime import API_REPOSITORY_METHODS
from app.models import User
from app.repositories.errors import IdempotencyConflict, InvalidStateTransition
from app.repositories.sqlalchemy_repository import SqlAlchemyRepository
from app.schemas.analysis import AnomalyJobRequest
from app.schemas.common import CurrentUser
from app.services.analysis import AnalysisService

pytestmark = pytest.mark.skipif(
    not all(callable(getattr(SqlAlchemyRepository, name, None)) for name in API_REPOSITORY_METHODS),
    reason="A3 job repository teslimi henüz yok",
)


@pytest.fixture
def job_case(db, astronaut):
    assert db.scalar(text("SELECT USER_NAME()")) == "astra_app"
    user = User(user_id=uuid4(), email=f"job-{uuid4().hex}@example.test",
                password_hash="TEST_ONLY_NOT_A_LOGIN_HASH", role="ASTRONAUT",
                is_active=True, astronaut_id=astronaut)
    db.add(user)
    db.flush()

    @contextmanager
    def transaction():
        with db.begin_nested():
            yield SqlAlchemyRepository(db)

    identity = CurrentUser(user_id=user.user_id, role="ASTRONAUT", astronaut_id=astronaut)
    return AnalysisService(transaction), identity


def test_real_job_creation_replay_conflict_and_scoped_status(db, job_case):
    service, identity = job_case
    body = AnomalyJobRequest(module="anomaly", idempotency_key=uuid4(), module_scope="combined")
    result = service.create(identity, body)
    assert result.created
    assert service.create(identity, body).response.job_id == result.response.job_id
    with pytest.raises(IdempotencyConflict):
        service.create(identity, body.model_copy(update={"module_scope": "physiological"}))
    assert service.get(identity, result.response.job_id).state == "QUEUED"
    assert db.scalar(text("SELECT COUNT(*) FROM ops.AnalysisJobs WHERE astronaut_id=:astronaut"),
                     {"astronaut": identity.astronaut_id}) == 1


def test_real_retry_preserves_snapshot_and_hash(db, job_case):
    service, identity = job_case
    body = AnomalyJobRequest(module="anomaly", idempotency_key=uuid4(), module_scope="combined")
    job_id = service.create(identity, body).response.job_id
    snapshot, digest = json.dumps({"records": [], "test_snapshot": True}), "a" * 64
    db.execute(text("UPDATE ops.AnalysisJobs SET state='FAILED', attempts=2, "
                    "error_code='MODEL_TIMEOUT', input_snapshot_json=:snapshot, input_hash=:digest "
                    "WHERE job_id=:job_id"),
               {"snapshot": snapshot, "digest": digest, "job_id": str(job_id)})
    assert service.retry(identity, job_id).state == "QUEUED"
    row = db.execute(text("SELECT input_snapshot_json,input_hash,attempts,retry_cycle "
                          "FROM ops.AnalysisJobs WHERE job_id=:job_id"), {"job_id": str(job_id)}).one()
    assert (row.input_snapshot_json, row.input_hash) == (snapshot, digest)
    assert (row.attempts, row.retry_cycle) == (0, 1)
    with pytest.raises(InvalidStateTransition):
        service.retry(identity, job_id)
