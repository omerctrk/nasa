"""Okuma servisi (Aybala): astronotun kendi geçmişi ve kulenin profil özetleri.

- Tarih aralıkları başlangıç DAHİL, bitiş HARİÇ [start, end); en fazla MAX_RANGE_DAYS.
- Astronot yalnız kendi verisini okur (astronaut_id girişten gelir).
- Kule iki demo profilini görür; haftalık ölçekler (WHO-5/PHQ-2/GAD-2) kuleye VERİLMEZ
  (paylaşım izni ayrı karar). Ortak ölçüm listesi zaten haftalık veriyi içermez.
- Yalnız okuma: commit yok.
"""
from __future__ import annotations

import datetime as dt
import json

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import Astronaut, Checkin, CognitiveTest, Oturum, TestKaydi, WeeklyAssessment
from app.repositories.errors import NotFound, ValidationFailed
from app.repositories.sqlalchemy_repository import SqlAlchemyRepository
from app.schemas.behavioral import CheckinOut, WeeklyOut
from app.schemas.common import MeasurementDTO, MeasurementModule
from app.schemas.readings import (
    CognitiveDetailOut,
    EyeSessionDetailOut,
    EyeTestOut,
    ProfileOut,
)
from app.services.data_entry import _aware, _checkin_out

MAX_RANGE_DAYS = 120


def check_range(start: dt.date, end: dt.date) -> None:
    if end <= start:
        raise ValidationFailed("end, start'tan sonra olmalı ([start, end) aralığı)")
    if (end - start).days > MAX_RANGE_DAYS:
        raise ValidationFailed(f"Aralık en fazla {MAX_RANGE_DAYS} gün olabilir")


def _profile(a: Astronaut) -> ProfileOut:
    return ProfileOut(
        astronaut_id=a.astronaut_id, display_name=a.display_name,
        is_display_only=a.is_display_only, mission_id=a.mission_id,
        mission_name=a.mission.name, mission_start_date=a.mission.start_date,
        mission_length_days=a.mission.length_days, scenario=a.mission.scenario,
    )


def _astronaut(db: Session, astronaut_id: str | None) -> Astronaut:
    a = db.scalars(
        select(Astronaut).options(joinedload(Astronaut.mission))
        .where(Astronaut.astronaut_id == astronaut_id)
    ).one_or_none() if astronaut_id else None
    if a is None:
        raise NotFound(str(astronaut_id))
    return a


def _start_end_dt(start: dt.date, end: dt.date) -> tuple[dt.datetime, dt.datetime]:
    return (dt.datetime.combine(start, dt.time()), dt.datetime.combine(end, dt.time()))


# --- Astronotun kendisi ----------------------------------------------------------------


def my_profile(db: Session, astronaut_id: str) -> ProfileOut:
    return _profile(_astronaut(db, astronaut_id))


def my_checkins(db: Session, astronaut_id: str, start: dt.date, end: dt.date) -> list[CheckinOut]:
    check_range(start, end)
    rows = db.scalars(
        select(Checkin).where(Checkin.astronaut_id == astronaut_id, Checkin.date >= start,
                              Checkin.date < end).order_by(Checkin.date)
    )
    return [_checkin_out(r) for r in rows]


def my_weekly(db: Session, astronaut_id: str, start: dt.date, end: dt.date) -> list[WeeklyOut]:
    check_range(start, end)
    s, e = _start_end_dt(start, end)
    rows = db.scalars(
        select(WeeklyAssessment).where(
            WeeklyAssessment.astronaut_id == astronaut_id, WeeklyAssessment.taken_at >= s,
            WeeklyAssessment.taken_at < e).order_by(WeeklyAssessment.taken_at, WeeklyAssessment.id)
    )
    return [WeeklyOut(id=r.id, taken_at=_aware(r.taken_at), mission_day=r.mission_day,
                      who5_score=r.who5_score, phq2_score=r.phq2_score, gad2_score=r.gad2_score,
                      share_with_crew_medical=r.share_with_crew_medical) for r in rows]


def my_cognitive(db: Session, astronaut_id: str, start: dt.date, end: dt.date,
                 test_type: str | None = None) -> list[CognitiveDetailOut]:
    check_range(start, end)
    s, e = _start_end_dt(start, end)
    stmt = select(CognitiveTest).where(
        CognitiveTest.astronaut_id == astronaut_id, CognitiveTest.taken_at >= s,
        CognitiveTest.taken_at < e)
    if test_type:
        stmt = stmt.where(CognitiveTest.test_type == test_type)
    rows = db.scalars(stmt.order_by(CognitiveTest.taken_at, CognitiveTest.id))
    # speed formülü teyitsiz: yanıt modelinde yok
    return [CognitiveDetailOut(
        id=r.id, taken_at=_aware(r.taken_at), mission_day=r.mission_day, test_type=r.test_type,
        duration_s=r.duration_s, n_trials=r.n_trials, mean_rt_ms=r.mean_rt_ms,
        median_rt_ms=r.median_rt_ms, lapses=r.lapses, false_starts=r.false_starts,
        accuracy=r.accuracy, correct_count=r.correct_count, valid=r.valid,
        invalid_reason=r.invalid_reason, device=r.device) for r in rows]


def my_eye_sessions(db: Session, astronaut_id: str, start_day: int,
                    end_day: int) -> list[EyeSessionDetailOut]:
    if end_day <= start_day or end_day - start_day > 400:
        raise ValidationFailed("Gün aralığı geçersiz ([start_day, end_day), en fazla 400 gün)")
    sessions = db.scalars(
        select(Oturum).where(Oturum.astronaut_id == astronaut_id,
                             Oturum.flight_day >= start_day, Oturum.flight_day < end_day)
        .order_by(Oturum.flight_day, Oturum.session_id)
    ).all()
    tests: dict[str, list[TestKaydi]] = {}
    if sessions:
        for t in db.scalars(select(TestKaydi).where(
                TestKaydi.session_id.in_([s.session_id for s in sessions]))
                .order_by(TestKaydi.test, TestKaydi.eye)):
            tests.setdefault(t.session_id, []).append(t)
    return [EyeSessionDetailOut(
        session_id=s.session_id, date=s.date, flight_day=s.flight_day, is_retest=s.is_retest,
        retest_of=s.retest_of, quality_score=s.quality_score, source=s.source,
        tests=[EyeTestOut(eye=t.eye.strip(), test=t.test, value=t.value, unit=t.unit,
                          amsler_cells=json.loads(t.amsler_cells) if t.amsler_cells else None,
                          n_correct=t.n_correct, n_presented=t.n_presented)
               for t in tests.get(s.session_id, [])],
    ) for s in sessions]


def measurements(db: Session, astronaut_id: str, start: dt.date, end: dt.date,
                 module: MeasurementModule | None = None) -> list[MeasurementDTO]:
    """Grafikler için ortak ölçüm listesi (anomaly.v_measurements)."""
    check_range(start, end)
    _astronaut(db, astronaut_id)  # yoksa 404
    rows = SqlAlchemyRepository(db).get_measurements(astronaut_id, start, end)
    return [m for m in rows if module is None or m.module is module]


# --- Kule -----------------------------------------------------------------------------------


def all_profiles(db: Session) -> list[ProfileOut]:
    rows = db.scalars(select(Astronaut).options(joinedload(Astronaut.mission))
                      .order_by(Astronaut.is_display_only, Astronaut.astronaut_id))
    return [_profile(a) for a in rows]
