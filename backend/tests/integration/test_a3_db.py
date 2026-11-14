"""A3 gerçek DB kabulü: iş yaşam döngüsü, lease, idempotency, alarm ve alındılar."""
import hashlib
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

from app.repositories.errors import (
    IdempotencyConflict,
    InvalidStateTransition,
    LeaseLost,
    SnapshotConflict,
)
from app.repositories.records import (
    AlertCreate,
    AnomalyResultData,
    JobOutcome,
    JobRequestData,
    JobScope,
    NotificationEventCreate,
)
from app.repositories.sqlalchemy_repository import SqlAlchemyRepository


def h(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


@pytest.fixture
def repo(db):
    r = SqlAlchemyRepository(db)
    r._retries, r._delay = 1, 0  # test: 1 otomatik tekrar, beklemesiz
    return r


@pytest.fixture
def scope(astronaut, users):
    return JobScope(user_id=users["astro"], role="ASTRONAUT", astronaut_id=astronaut)


def claim_mine(repo, job_id):
    """DB'de başka QUEUED iş varsa onları atlayıp kendi işimizi bul (hepsi rollback olur)."""
    for _ in range(50):
        c = repo.claim_next_job(lease_seconds=120)
        if c is None or c.job.job_id == job_id:
            return c
    raise AssertionError("iş sahiplenilemedi")


ANOMALY = JobRequestData(module="anomaly", module_scope="combined")


def test_idempotency(repo, scope):
    key = uuid.uuid4()
    a = repo.create_or_get_job(scope, key, h("1"), ANOMALY)
    b = repo.create_or_get_job(scope, key, h("1"), ANOMALY)
    assert a.created and not b.created and a.job.job_id == b.job.job_id
    assert b.job.request == ANOMALY  # request_json geri okunur
    with pytest.raises(IdempotencyConflict):
        repo.create_or_get_job(scope, key, h("2"), ANOMALY)


def test_lifecycle_snapshot_and_lease(repo, scope, db):
    job = repo.create_or_get_job(scope, uuid.uuid4(), h("x"), ANOMALY).job
    c = claim_mine(repo, job.job_id)
    assert c.job.state == "SYNCING" and c.job.attempts == 1 and c.input_snapshot is None
    assert repo.renew_job_lease(job.job_id, c.lease_token, 120)
    assert not repo.renew_job_lease(job.job_id, uuid.uuid4(), 120)

    repo.save_input_snapshot(job.job_id, c.lease_token, {"v": 1}, h("s1"))
    repo.save_input_snapshot(job.job_id, c.lease_token, {"v": 1}, h("s1"))  # aynı: no-op
    with pytest.raises(SnapshotConflict):
        repo.save_input_snapshot(job.job_id, c.lease_token, {"v": 2}, h("s2"))
    with pytest.raises(LeaseLost):
        repo.save_input_snapshot(job.job_id, uuid.uuid4(), {"v": 1}, h("s1"))

    rid = repo.save_anomaly_result(AnomalyResultData(
        astronaut_id=scope.astronaut_id, mission_day=74, module_scope="combined",
        model_version="mock", is_anomaly=False, level="normal", summary="ok", drivers=[],
        baseline_status="provisional", data_quality_status="valid", recommendation="-",
        data_cutoff_at=datetime.now(UTC) - timedelta(minutes=1)))
    done = repo.finalize_job(job.job_id, c.lease_token, JobOutcome(
        state="COMPLETED", evaluation_status="evaluated", anomaly_result_id=rid))
    assert done.state == "COMPLETED" and done.anomaly_result_id == rid
    with pytest.raises(LeaseLost):  # lease temizlendi
        repo.finalize_job(job.job_id, c.lease_token, JobOutcome(state="FAILED"))


def test_expired_lease_is_recovered_then_failed(repo, scope, db):
    job = repo.create_or_get_job(scope, uuid.uuid4(), h("r"), ANOMALY).job
    expire = text("UPDATE ops.AnalysisJobs SET lease_until = DATEADD(second,-1,SYSUTCDATETIME())"
                  " WHERE job_id = :j")
    claim_mine(repo, job.job_id)
    db.execute(expire, {"j": str(job.job_id)})
    rec = {r.job_id: r for r in repo.recover_expired_jobs()}
    assert rec[job.job_id].new_state == "QUEUED"  # 1. deneme → otomatik tekrar
    claim_mine(repo, job.job_id)
    db.execute(expire, {"j": str(job.job_id)})
    rec = {r.job_id: r for r in repo.recover_expired_jobs()}
    assert rec[job.job_id].new_state == "FAILED"  # tekrar hakkı bitti

    again = repo.request_retry(job.job_id, scope)
    assert again.state == "QUEUED" and again.retry_cycle == 1 and again.attempts == 0
    with pytest.raises(InvalidStateTransition):
        repo.request_retry(job.job_id, scope)


def test_sans_job_is_never_auto_retried(repo, scope, db):
    job = repo.create_or_get_job(scope, uuid.uuid4(), h("s"), JobRequestData(
        module="sans", session_id="S-X")).job
    claim_mine(repo, job.job_id)
    db.execute(text("UPDATE ops.AnalysisJobs SET lease_until = DATEADD(second,-1,"
                    "SYSUTCDATETIME()) WHERE job_id = :j"), {"j": str(job.job_id)})
    rec = {r.job_id: r for r in repo.recover_expired_jobs()}
    assert rec[job.job_id].new_state == "FAILED"


def test_alert_ack_resolve_and_receipts(repo, scope, users):
    rid = repo.save_anomaly_result(AnomalyResultData(
        astronaut_id=scope.astronaut_id, mission_day=74, module_scope="combined",
        model_version="mock", is_anomaly=True, level="watch", summary="x", drivers=[],
        baseline_status="provisional", data_quality_status="valid", recommendation="-",
        data_cutoff_at=datetime.now(UTC) - timedelta(minutes=1)))
    new = AlertCreate(astronaut_id=scope.astronaut_id, module="anomaly", severity="WARNING",
                      anomaly_result_id=rid)
    a1, a2 = repo.create_alert(new), repo.create_alert(new)
    assert a1.alert_id == a2.alert_id and a1.status == "OPEN"  # sonuç başına tek alarm

    with pytest.raises(InvalidStateTransition):
        repo.resolve_alert(a1.alert_id, users["ground1"], "erken")
    first = repo.acknowledge_alert(a1.alert_id, users["ground1"])
    second = repo.acknowledge_alert(a1.alert_id, users["ground2"])
    assert second.acknowledged_by == first.acknowledged_by == users["ground1"]
    closed = repo.resolve_alert(a1.alert_id, users["ground2"], "  incelendi  ")
    assert closed.status == "RESOLVED" and closed.resolution_note == "incelendi"

    ev = NotificationEventCreate(event_type="risk.alert.created", audience="GROUND_CONTROL",
                                 target_user_id=None, alert_id=a1.alert_id, payload={"a": 1})
    e1, e2 = repo.create_notification_event(ev), repo.create_notification_event(ev)
    assert e1.event_id == e2.event_id
    assert e1.event_id in {e.event_id for e in repo.list_pending_events(users["ground1"])}
    assert repo.list_pending_events(users["astro"]) == []  # astronota kule olayı gitmez
    repo.mark_event_sent(e1.event_id)
    assert repo.record_receipt(e1.event_id, users["ground1"]) is True
    assert repo.record_receipt(e1.event_id, users["ground1"]) is False
    assert e1.event_id not in {e.event_id for e in repo.list_pending_events(users["ground1"])}
    assert e1.event_id in {e.event_id for e in repo.list_pending_events(users["ground2"])}
