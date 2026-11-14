"""Ö3 SQL acceptance after A3; never creates tables or runs migrations."""

from uuid import uuid4

import pytest
from sqlalchemy import text

from app.core.worker_runtime import WORKER_REPOSITORY_METHODS
from app.models import User
from app.repositories.errors import LeaseLost
from app.repositories.records import JobOutcome, JobRequestData, JobScope
from app.repositories.sqlalchemy_repository import SqlAlchemyRepository
from app.services.analysis import canonical_request_hash
from app.workers.analysis import snapshot_hash

pytestmark = pytest.mark.skipif(
    not all(callable(getattr(SqlAlchemyRepository, method, None)) for method in WORKER_REPOSITORY_METHODS),
    reason="A3 worker repository metotları teslim edilmedi",
)


@pytest.fixture
def queued_job(db, astronaut):
    assert db.scalar(text("SELECT USER_NAME()")) == "astra_app"
    user = User(user_id=uuid4(), email=f"worker-{uuid4().hex}@example.test",
                password_hash="TEST_ONLY_NOT_A_LOGIN_HASH", role="ASTRONAUT",
                is_active=True, astronaut_id=astronaut)
    db.add(user)
    db.flush()
    repo = SqlAlchemyRepository(db)
    scope = JobScope(user_id=user.user_id, role="ASTRONAUT", astronaut_id=astronaut)
    request = JobRequestData(module="anomaly", module_scope="combined")
    job = repo.create_or_get_job(scope, uuid4(), canonical_request_hash(request), request).job
    return repo, scope, job


def test_real_claim_snapshot_and_delayed_retry(db, queued_job):
    repo, scope, job = queued_job
    claim = repo.claim_next_job(120)
    assert claim.job.job_id == job.job_id
    assert claim.job.attempts == 1 and claim.job.state == "SYNCING"
    snapshot = {"records": [], "test_only": True}
    digest = snapshot_hash(snapshot)
    repo.save_input_snapshot(job.job_id, claim.lease_token, snapshot, digest)
    assert repo.renew_job_lease(job.job_id, claim.lease_token, 120)
    repo.reschedule_job(job.job_id, claim.lease_token, 60, "MODEL_TIMEOUT", 2)
    record = repo.get_job(job.job_id, scope)
    assert record.state == "QUEUED" and record.has_snapshot
    row = db.execute(text("SELECT input_hash,input_snapshot_json,lease_token,lease_until "
                          "FROM ops.AnalysisJobs WHERE job_id=:job_id"), {"job_id": str(job.job_id)}).one()
    assert row.input_hash == digest and row.input_snapshot_json
    assert row.lease_token is None and row.lease_until is None


def test_real_expired_lease_is_not_renewed_and_is_recovered(db, queued_job):
    repo, scope, job = queued_job
    claim = repo.claim_next_job(120)
    assert claim.job.job_id == job.job_id
    db.execute(text("UPDATE ops.AnalysisJobs SET lease_until=DATEADD(second,-1,SYSUTCDATETIME()) "
                    "WHERE job_id=:job_id"), {"job_id": str(job.job_id)})
    assert not repo.renew_job_lease(job.job_id, claim.lease_token, 120)
    with pytest.raises(LeaseLost):
        repo.finalize_job(job.job_id, claim.lease_token, JobOutcome(state="FAILED", error_code="TEST_ONLY"))
    recovered = repo.recover_expired_jobs(2)
    assert job.job_id in {item.job_id for item in recovered}
    assert repo.get_job(job.job_id, scope).state == "QUEUED"
