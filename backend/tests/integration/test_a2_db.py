"""A2 gerçek DB kabulü: CHECK/FK kuralları, astra_app izinleri, sonuç repository'si."""
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.models import Oturum, TestKaydi
from app.repositories.records import AnomalyResultData, SansAnalysisData, SansStateData
from app.repositories.sqlalchemy_repository import SqlAlchemyRepository


def oturum(astronaut_id, sid, day, **kw):
    base = dict(session_id=sid, astronaut_id=astronaut_id, date=date(2027, 1, 5) + timedelta(days=day),
                flight_day=day, is_retest=False, retest_of=None, quality_score=Decimal("0.9"),
                source="synthetic")
    return Oturum(**(base | kw))


def test_runs_as_limited_account(db):
    assert db.scalar(text("SELECT USER_NAME()")) == "astra_app"


def test_preflight_negative_day_and_retest(db, astronaut):
    db.add(oturum(astronaut, f"S-{astronaut}-M60", -60))
    db.add(oturum(astronaut, f"S-{astronaut}-D74", 74))
    db.flush()
    db.add(oturum(astronaut, f"S-{astronaut}-D75", 75, is_retest=True, retest_of=f"S-{astronaut}-D74"))
    db.flush()


def test_retest_without_link_is_rejected(db, astronaut):
    with pytest.raises(IntegrityError), db.begin_nested():
        db.add(oturum(astronaut, f"S-{astronaut}-X", 75, is_retest=True))


def test_test_unit_mismatch_is_rejected(db, astronaut):
    db.add(oturum(astronaut, f"S-{astronaut}-D74", 74))
    db.flush()
    with pytest.raises(IntegrityError), db.begin_nested():
        db.add(TestKaydi(session_id=f"S-{astronaut}-D74", astronaut_id=astronaut, flight_day=74,
                         eye="OD", test="contrast", value=Decimal("1.5"), unit="logMAR"))


def test_app_cannot_delete(db, astronaut):
    with pytest.raises(DBAPIError, match="DELETE permission"), db.begin_nested():
        db.execute(text("DELETE FROM sans.analiz WHERE 1=0"))


def test_save_results_and_state(db, astronaut):
    repo = SqlAlchemyRepository(db)
    db.add(oturum(astronaut, f"S-{astronaut}-D74", 74))
    db.flush()

    a1 = repo.save_sans_analysis(SansAnalysisData(
        astronaut_id=astronaut, session_id=f"S-{astronaut}-D74", flight_day=74,
        risk=Decimal("0.5"), level="yellow", state="suspect", drivers=[{"m": "contrast"}]))
    assert repo.update_sans_state(SansStateData(
        astronaut_id=astronaut, state="suspect", since_flight_day=74, retest_due_day=75,
        last_analysis_id=a1), expected_last_analysis_id=None)

    a2 = repo.save_sans_analysis(SansAnalysisData(
        astronaut_id=astronaut, session_id=None, flight_day=75, risk=Decimal("0.9"),
        level="red", state="confirmed"))
    new = SansStateData(astronaut_id=astronaut, state="confirmed", since_flight_day=75,
                        retest_due_day=None, last_analysis_id=a2)
    assert repo.update_sans_state(new, expected_last_analysis_id=999_999) is False  # eski referans
    assert repo.update_sans_state(new, expected_last_analysis_id=a1) is True
    assert repo.update_sans_state(new, expected_last_analysis_id=None) is False  # zaten var

    rid = repo.save_anomaly_result(AnomalyResultData(
        astronaut_id=astronaut, mission_day=74, module_scope="combined", model_version="mock",
        is_anomaly=True, level="watch", summary="test", drivers=[], baseline_status="provisional",
        data_quality_status="valid", recommendation="izle",
        data_cutoff_at=datetime.now(UTC) - timedelta(minutes=1)))
    assert rid
