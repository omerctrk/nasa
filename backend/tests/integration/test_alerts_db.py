"""Ö6 kalıcı yazım + sonuç/alarm uçları + bildirim olayları, gerçek MS SQL'de."""
import hashlib
import uuid
from datetime import date, timedelta
from pathlib import Path

import pytest

from app.repositories.errors import InvalidStateTransition, NotFound
from app.repositories.records import JobRequestData, JobScope
from app.repositories.sqlalchemy_repository import SqlAlchemyRepository
from app.schemas.common import AlertStatus, AnomalyLevel, EventType
from app.services import alerts as svc
from app.services.anomaly import evaluate_snapshot, load_cards, persist_evaluation

CARDS = load_cards(Path(__file__).resolve().parents[2] / "config/knowledge_cards.json")


@pytest.fixture
def job(db, astronaut, users):
    scope = JobScope(user_id=users["astro"], role="ASTRONAUT", astronaut_id=astronaut)
    request = JobRequestData(module="anomaly", module_scope="physiological")
    key = uuid.uuid4()
    digest = hashlib.sha256(key.bytes).hexdigest()
    return SqlAlchemyRepository(db).create_or_get_job(scope, key, digest, request).job


def snapshot(astronaut, status, value="72"):
    breached = {"within_range": False}.get(status, True)
    return {"module": "anomaly", "data_cutoff_at": "2026-01-01T07:59:00.000Z",  # geçmiş: DB, kesim ≤ oluşturma kuralını uygular
            "model_input": {
                "astronaut_id": astronaut, "module_scope": "physiological",
                "threshold_policy_version": "t-1",
                "current_measurements": [{"record_id": "r1", "module": "physiological",
                                          "measurement": "blood_glucose", "unit": "mg/dL",
                                          "value_num_exact": value, "measured_date": "2027-03-14"}],
                "threshold_findings": [{"record_id": "r1", "policy_version": "t-1", "status": status,
                                        "breached": breached, "lower": "70", "upper": "180",
                                        "value_minus_bound": "70" if breached else None,
                                        "absolute_deviation": None}]}}


def test_persist_review_writes_result_alert_events_and_reads_back(db, astronaut, users, job):
    repo = SqlAlchemyRepository(db)
    ev = evaluate_snapshot(job, snapshot(astronaut, "above_range", "250"), CARDS)
    assert ev.result.level is AnomalyLevel.REVIEW
    out = persist_evaluation(repo, job, ev)
    db.flush()

    mine = svc.result(db, out.anomaly_result_id, astronaut_id=astronaut)
    assert mine.level is AnomalyLevel.REVIEW and mine.drivers[0]["measurement"] == "blood_glucose"
    with pytest.raises(NotFound):  # başka astronotun sonucu görünmez
        svc.result(db, out.anomaly_result_id, astronaut_id="A-baska")
    today = date.today()
    listed = svc.results(db, astronaut, today, today + timedelta(days=1))
    assert [r.id for r in listed] == [out.anomaly_result_id]

    open_alerts = svc.alerts(db, [AlertStatus.OPEN], astronaut)
    assert len(open_alerts) == 1 and open_alerts[0].severity.value == "WARNING"
    mine = [e for e in repo.list_pending_events(users["astro"])
            if e.alert_id == open_alerts[0].alert_id]
    assert [e.event_type for e in mine] == [EventType.RISK_ALERT_CREATED]  # tamamlanma olayı yok
    ground_events = [e for e in repo.list_pending_events(users["ground1"])
                     if e.alert_id == open_alerts[0].alert_id]
    assert [e.event_type for e in ground_events] == [EventType.RISK_ALERT_CREATED]


def test_acknowledge_then_resolve(db, astronaut, users, job):
    repo = SqlAlchemyRepository(db)
    out = persist_evaluation(repo, job, evaluate_snapshot(job, snapshot(astronaut, "above_range", "250"), CARDS))
    alert_id = svc.alerts(db, None, astronaut)[0].alert_id
    assert out.anomaly_result_id

    with pytest.raises(InvalidStateTransition):  # onaysız kapatılamaz
        svc.resolve(db, alert_id, users["ground1"], "not")
    acked = svc.acknowledge(db, alert_id, users["ground1"])
    assert acked.status is AlertStatus.ACKNOWLEDGED and acked.acknowledged_by == users["ground1"]
    again = svc.acknowledge(db, alert_id, users["ground2"])  # ilk onaylayan korunur
    assert again.acknowledged_by == users["ground1"]
    done = svc.resolve(db, alert_id, users["ground2"], "Hekimle görüşüldü")
    assert done.status is AlertStatus.RESOLVED and done.resolution_note == "Hekimle görüşüldü"
    assert svc.alerts(db, [AlertStatus.OPEN], astronaut) == []


def test_normal_result_has_no_alert(db, astronaut, users, job):
    repo = SqlAlchemyRepository(db)
    out = persist_evaluation(repo, job, evaluate_snapshot(job, snapshot(astronaut, "within_range"), CARDS))
    assert svc.result(db, out.anomaly_result_id).level is AnomalyLevel.NORMAL
    assert svc.alerts(db, None, astronaut) == []
    done = [e for e in SqlAlchemyRepository(db).list_pending_events(users["astro"])
            if e.job_id == job.job_id]
    assert [e.event_type for e in done] == [EventType.ANALYSIS_COMPLETED]
