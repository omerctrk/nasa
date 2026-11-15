"""A5 gerçek DB kabulü: VIEW'lar, ortak DTO, SANS bağlamında gelecek verinin dışlanması."""
import uuid
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import text

from app.models import (
    Checkin,
    CognitiveTest,
    MeasurementDefinition,
    Ortam,
    Oturum,
    Semptom,
    TestKaydi,
)
from app.repositories.sqlalchemy_measurements import MissingDefinition
from app.repositories.sqlalchemy_repository import SqlAlchemyRepository

CODES = {  # (module, unit, kind, worsening)
    "mood": ("behavioral", "score_0_10", "integer", "unconfirmed"),
    "energy": ("behavioral", "score_0_10", "integer", "unconfirmed"),
    "stress": ("behavioral", "score_0_10", "integer", "unconfirmed"),
    "loneliness": ("behavioral", "score_0_4", "integer", "unconfirmed"),
    "crew": ("behavioral", "score_0_4", "integer", "unconfirmed"),
    "mood_index": ("behavioral", "score_0_100", "numeric", "unconfirmed"),
    "sleep_hours": ("behavioral", "h", "numeric", "unconfirmed"),
    "sleep_quality": ("behavioral", "score_1_5", "integer", "unconfirmed"),
    "pvt_mean_rt": ("behavioral", "ms", "numeric", "unconfirmed"),
    "pvt_median_rt": ("behavioral", "ms", "numeric", "unconfirmed"),
    "pvt_lapses": ("behavioral", "count", "integer", "unconfirmed"),
    "pvt_false_starts": ("behavioral", "count", "integer", "unconfirmed"),
    "near_acuity": ("sans", "logMAR", "numeric", "higher"),
    "contrast": ("sans", "logCS", "numeric", "lower"),
    "amsler": ("sans", "cells", "integer", "higher"),
}


@pytest.fixture
def dictionary(db):
    """Sözlük (A6 seed'i yoksa test için ekler; varsa dokunmaz). Rollback ile kalkar."""
    have = set(db.scalars(text("SELECT measurement_code FROM anomaly.MeasurementDefinitions")))
    for code, (module, unit, kind, worse) in CODES.items():
        if code not in have:
            db.add(MeasurementDefinition(measurement_code=code, module=module, canonical_unit=unit,
                                         value_kind=kind, protocol_version="test-v1",
                                         worsening_direction=worse))
    db.flush()


def test_views_readable_by_app(db):
    for v in ("sans.gorev", "sans.profil", "anomaly.v_measurements"):
        db.execute(text(f"SELECT TOP 1 * FROM {v}"))


def add_data(db, a):
    db.add(Checkin(date=date(2027, 3, 19), mission_day=73, mood=6, energy=5, stress=4,
                   loneliness=1, crew=3, mood_index=60.0, bed_time=time(23), wake_time=time(7),
                   sleep_hours=8.0, sleep_quality=4, source="seed",
                   created_at=datetime(2027, 3, 19, 8), updated_at=datetime(2027, 3, 19, 8),
                   astronaut_id=a))
    db.add(CognitiveTest(taken_at=datetime(2027, 3, 19, 9, 30), mission_day=73, test_type="pvt",
                         duration_s=180, n_trials=50, mean_rt_ms=310.0, median_rt_ms=300.0,
                         speed=3.2, lapses=2, false_starts=0, valid=True, device="tablet",
                         raw="[]", source="manual", astronaut_id=a,
                         client_request_id=uuid.uuid4()))
    for sid, day in ((f"S-{a}-M60", -60), (f"S-{a}-D74", 74), (f"S-{a}-D75", 75)):
        db.add(Oturum(session_id=sid, astronaut_id=a, date=date(2027, 1, 5) + timedelta(days=day),
                      flight_day=day, is_retest=day == 75,
                      retest_of=f"S-{a}-D74" if day == 75 else None,
                      quality_score=Decimal("0.9"), source="test_screen"))
        db.flush()
        for eye in ("OD", "OS"):
            db.add(TestKaydi(session_id=sid, astronaut_id=a, flight_day=day, eye=eye,
                             test="near_acuity", value=Decimal("-0.05"), unit="logMAR"))
    db.add(Semptom(astronaut_id=a, flight_day=74, headache=True))
    db.add(Semptom(astronaut_id=a, flight_day=75, headache=False))
    db.flush()


def test_get_measurements(db, astronaut, dictionary):
    add_data(db, astronaut)
    repo = SqlAlchemyRepository(db)
    ms = repo.get_measurements(astronaut, date(2027, 3, 19), date(2027, 3, 20))
    ids = {m.record_id for m in ms}
    assert any(i.endswith(":stress") and i.startswith("checkin:") for i in ids)
    assert any(i.endswith(":pvt_mean_rt") for i in ids)
    assert not any("speed" in i for i in ids)
    checkin = next(m for m in ms if m.measurement == "mood")
    assert checkin.source == "synthetic" and checkin.metadata_json == {"original_source": "seed"}
    assert checkin.measured_at is None and checkin.time_precision == "date"
    pvt = next(m for m in ms if m.measurement == "pvt_mean_rt")
    assert pvt.time_precision == "timestamp" and pvt.measured_at.tzinfo is not None
    assert repo.get_measurements(astronaut, date(2027, 3, 20), date(2027, 3, 20)) == []  # [s, e)


def test_missing_definition_reported(db, astronaut):
    db.add(Checkin(date=date(2027, 3, 1), mission_day=55, mood=6, energy=5, stress=4,
                   loneliness=1, crew=3, mood_index=60.0, bed_time=time(23), wake_time=time(7),
                   sleep_hours=8.0, sleep_quality=4, source="manual",
                   created_at=datetime(2027, 3, 1), updated_at=datetime(2027, 3, 1),
                   astronaut_id=astronaut))
    db.flush()
    have = set(db.scalars(text("SELECT measurement_code FROM anomaly.MeasurementDefinitions")))
    if {"mood", "energy"} <= have:
        pytest.skip("sözlük zaten dolu (seed çalışmış)")
    with pytest.raises(MissingDefinition):
        SqlAlchemyRepository(db).get_measurements(astronaut, date(2027, 3, 1), date(2027, 3, 2))


def test_sans_context_excludes_future(db, astronaut, dictionary):
    add_data(db, astronaut)
    db.add(Ortam(mission_id=db.scalar(text("SELECT mission_id FROM core.Astronauts WHERE astronaut_id=:a"),
                                      {"a": astronaut}), day=74, co2_mmhg=Decimal("2.5"), source="synthetic"))
    db.flush()
    ctx = SqlAlchemyRepository(db).get_sans_context(astronaut, f"S-{astronaut}-D74",
                                                    datetime.now(UTC))
    assert ctx.session.flight_day == 74
    assert [s.flight_day for s in ctx.baseline_sessions] == [-60]
    assert {m.mission_day for m in ctx.eye_history} == {-60, 74}  # 75 (gelecek) yok
    assert {m.eye for m in ctx.eye_history} == {"OD", "OS"}
    assert [s.flight_day for s in ctx.symptoms] == [74]
    assert ctx.state is None
    assert SqlAlchemyRepository(db).get_sans_context("YOK", f"S-{astronaut}-D74",
                                                     datetime.now(UTC)) is None
