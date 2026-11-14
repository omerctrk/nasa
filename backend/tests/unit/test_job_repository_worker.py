"""Exercise the real A3 repository methods without an ODBC connection."""

import inspect
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest
from sqlalchemy.dialects import mssql

from app.repositories.errors import InvalidStateTransition, LeaseLost, RepositoryError, ValidationFailed
from app.repositories.interfaces import JobRepository
from app.repositories.records import JobOutcome
from app.repositories.sqlalchemy_jobs import SqlAlchemyJobRepository
from app.repositories.sqlalchemy_repository import SqlAlchemyRepository


def sql(statement):
    return str(statement.compile(dialect=mssql.dialect()))


@pytest.fixture
def case():
    session = Mock()
    repo = SqlAlchemyJobRepository(session, anomaly_auto_retries=1, anomaly_retry_delay_seconds=2)
    now, job_id, token = datetime.now(UTC), uuid4(), uuid4()
    row = SimpleNamespace(job_id=job_id, astronaut_id="A007", module="anomaly", state="SYNCING",
                          request_json='{"module":"anomaly","module_scope":"combined"}',
                          attempts=1, retry_cycle=0, input_snapshot_json='{"v":1}', input_hash="a" * 64,
                          evaluation_status=None, error_code=None, anomaly_result_id=None,
                          sans_analysis_id=None, created_at=now, updated_at=now,
                          lease_token=token, lease_until=now + timedelta(seconds=120))
    return repo, session, row


def test_actual_worker_methods_match_shared_parameter_names():
    for method in ["claim_next_job", "renew_job_lease", "recover_expired_jobs", "reschedule_job",
                   "save_input_snapshot", "finalize_job"]:
        expected = inspect.signature(getattr(JobRepository, method))
        actual = inspect.signature(getattr(SqlAlchemyRepository, method))
        assert list(actual.parameters) == list(expected.parameters)


@pytest.mark.parametrize(("configured", "requested", "effective"), [(1, 2, 2), (0, 2, 1), (1, 1, 1)])
def test_recovery_accepts_worker_limit_and_preserves_stricter_config(case, configured, requested, effective):
    repo, session, _ = case
    repo._retries = configured
    session.execute.return_value.all.return_value = []
    assert repo.recover_expired_jobs(requested) == []
    statement, params = session.execute.call_args.args
    assert params == {"limit": effective, "delay": 2000}
    assert "attempts < :limit" in str(statement)
    assert "SANS_RECONCILIATION_REQUIRED" in str(statement)
    assert "lease_until <= SYSUTCDATETIME()" in str(statement)


def test_reschedule_is_conditional_and_does_not_overwrite_snapshot(case):
    repo, session, row = case
    session.execute.return_value.rowcount = 1
    repo._load = Mock(return_value=row)
    result = repo.reschedule_job(row.job_id, row.lease_token, 2, "MODEL_TIMEOUT", 2)
    statement, params = session.execute.call_args.args
    query = sql(statement)
    assert result.job_id == row.job_id
    assert params == {"delay_ms": 2000}
    assert "lease_until > SYSUTCDATETIME()" in query
    assert "attempts <" in query and "module =" in query
    assignments = query.split(" SET ")[1].split(" WHERE ")[0]
    assert "input_snapshot_json=" not in assignments and "input_hash=" not in assignments
    assert "request_json=" not in assignments and "attempts=" not in assignments
    session.commit.assert_not_called()


def test_reschedule_distinguishes_lease_loss_and_ineligible_job(case):
    repo, session, row = case
    session.execute.return_value.rowcount = 0
    repo._load_owned = Mock(return_value=None)
    with pytest.raises(LeaseLost):
        repo.reschedule_job(row.job_id, row.lease_token, 2, "MODEL_TIMEOUT")
    repo._load_owned.return_value = row
    with pytest.raises(InvalidStateTransition):
        repo.reschedule_job(row.job_id, row.lease_token, 2, "MODEL_TIMEOUT")


@pytest.mark.parametrize("updates", [{"delay_seconds": -1}, {"delay_seconds": float("inf")},
                                      {"max_attempts": 3}, {"error_code": "RAW SQL SECRET"}])
def test_invalid_retry_parameters_never_reach_sql(case, updates):
    repo, session, row = case
    args = dict(job_id=row.job_id, lease_token=row.lease_token, delay_seconds=2,
                error_code="MODEL_TIMEOUT", max_attempts=2) | updates
    with pytest.raises(ValidationFailed):
        repo.reschedule_job(**args)
    session.execute.assert_not_called()


def test_claim_lock_contention_does_not_claim_a_row(case):
    repo, session, _ = case
    session.execute.return_value.scalar_one.return_value = -1
    assert repo.claim_next_job(120) is None
    assert session.execute.call_count == 1
    query = str(session.execute.call_args.args[0])
    assert "sp_getapplock" in query and "@LockOwner=N'Transaction'" in query
    assert "@DbPrincipal=N'public'" in query
    assert "SET NOCOUNT ON" not in query  # later lease UPDATEs rely on ODBC rowcount


@pytest.mark.parametrize("status", [-2, -3, -999])
def test_claim_lock_errors_propagate_for_transaction_rollback(case, status):
    repo, session, _ = case
    session.execute.return_value.scalar_one.return_value = status
    with pytest.raises(RepositoryError):
        repo.claim_next_job(120)
    assert session.execute.call_count == 1


def test_claim_sql_excludes_same_astronaut_active_sans(case):
    repo, session, row = case
    session.execute.side_effect = [Mock(scalar_one=lambda: 0),
                                   Mock(scalar_one_or_none=lambda: str(row.job_id))]
    repo._load = Mock(return_value=row)
    claimed = repo.claim_next_job(120)
    assert claimed.job.job_id == row.job_id
    query = str(session.execute.call_args_list[1].args[0])
    assert "NOT EXISTS" in query
    assert "active_sans.astronaut_id = queued.astronaut_id" in query
    assert "active_sans.state IN ('SYNCING', 'ANALYZING')" in query
    session.commit.assert_not_called()


def test_initial_snapshot_update_includes_expiry_guard(case):
    repo, session, row = case
    session.execute.return_value.rowcount = 1
    repo.save_input_snapshot(row.job_id, row.lease_token, {"v": 1}, "a" * 64)
    assert "lease_until > SYSUTCDATETIME()" in sql(session.execute.call_args.args[0])


def test_snapshot_retry_checks_expiry_again_after_loading(case):
    repo, session, row = case
    session.execute.return_value.rowcount = 0
    repo._load_owned = Mock(return_value=row)
    with pytest.raises(LeaseLost):
        repo.save_input_snapshot(row.job_id, row.lease_token, {"v": 1}, "a" * 64)
    assert session.execute.call_count == 2
    assert "lease_until > SYSUTCDATETIME()" in sql(session.execute.call_args.args[0])


def test_finalization_update_rechecks_expiry_at_write_time(case):
    repo, session, row = case
    repo._load_owned = Mock(return_value=row)
    session.execute.return_value.rowcount = 0
    with pytest.raises(LeaseLost):
        repo.finalize_job(row.job_id, row.lease_token, JobOutcome(state="FAILED", error_code="TEST_ONLY"))
    assert "lease_until > SYSUTCDATETIME()" in sql(session.execute.call_args.args[0])
