"""Veri girişi servisi (A7, sahip: Aybala).

Ortak kurallar:
- astronaut_id doğrulanmış kullanıcıdan gelir; gösterim profili (is_display_only=1) yazamaz → 403.
- mission_day backend'de hesaplanır: tarih − görev günü 0.
- Tekrar güvenliği: aynı client_request_id / aynı oturum + AYNI içerik → mevcut kayıt
  (created=False); farklı içerik → 409. Tekillik DB UNIQUE kuralıyla sağlanır.
- Check-in kişi+gün tek satırdır; güncelleme If-Match (ETag) ister, eskiyse 412.
- Baş ağrısının tek kaynağı sans.semptom; check-in'e yazılmaz.
- Commit bu katmanda yapılır (repository yapmaz); hata olursa tamamı geri alınır.
"""
from __future__ import annotations

import datetime as dt
import json
import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    Astronaut,
    Checkin,
    CognitiveTest,
    MeasurementDefinition,
    MeasurementRecord,
    Oturum,
    Semptom,
    TestKaydi,
    WeeklyAssessment,
)
from app.repositories.errors import (
    Forbidden,
    IdempotencyConflict,
    NotFound,
    PreconditionFailed,
    ValidationFailed,
)
from app.repositories.sqlalchemy_results import to_json
from app.schemas.behavioral import (
    CheckinIn,
    CheckinOut,
    CognitiveIn,
    CognitiveOut,
    WeeklyIn,
    WeeklyOut,
    sleep_hours_between,
)
from app.schemas.common import CurrentUser
from app.schemas.measurements import PhysiologicalIn, PhysiologicalOut
from app.schemas.sans import (
    EyeSessionIn,
    EyeSessionOut,
    HeadacheIn,
    HeadacheOut,
)

NOW = func.sysutcdatetime()


# --- yardımcılar -----------------------------------------------------------------------


def _naive_ms(v: dt.datetime) -> dt.datetime:
    """DATETIME2(3) ile aynı hassasiyet: UTC, saat dilimsiz, milisaniye."""
    if v.tzinfo is not None:
        v = v.astimezone(dt.UTC).replace(tzinfo=None)
    return v.replace(microsecond=(v.microsecond // 1000) * 1000)


def _aware(v: dt.datetime) -> dt.datetime:
    return v.replace(tzinfo=dt.UTC) if v.tzinfo is None else v


def etag_of(updated_at: dt.datetime) -> str:
    return f'"{int(_aware(updated_at).timestamp() * 1000)}"'


def _writer(db: Session, user: CurrentUser) -> Astronaut:
    astro = db.get(Astronaut, user.astronaut_id) if user.astronaut_id else None
    if astro is None:
        raise Forbidden("Astronot profili bulunamadı")
    if astro.is_display_only:
        raise Forbidden("Gösterim profiline veri girilemez")
    return astro


def _day(astro: Astronaut, d: dt.date) -> int:
    return (d - astro.mission.start_date).days


def _same(stored: dict[str, Any], wanted: dict[str, Any]) -> bool:
    return all(stored.get(k) == v for k, v in wanted.items())


def _insert_or_replay(db: Session, row: Any, find, wanted: dict[str, Any], as_dict) -> tuple[Any, bool]:
    """Ekle; UNIQUE çakışmasında mevcut kaydı oku: aynı içerik → (mevcut, False), farklı → 409."""
    try:
        with db.begin_nested():
            db.add(row)
        return row, True
    except IntegrityError:
        existing = find()
        if existing is None:
            raise  # FK vb. gerçek hata gizlenmez
        if not _same(as_dict(existing), wanted):
            raise IdempotencyConflict("Aynı istek anahtarı farklı içerikle kullanıldı") from None
        return existing, False


# --- Check-in --------------------------------------------------------------------------


def _checkin_out(r: Checkin) -> CheckinOut:
    return CheckinOut(
        date=r.date, mission_day=r.mission_day, mood=r.mood, energy=r.energy, stress=r.stress,
        loneliness=r.loneliness, crew=r.crew, mood_index=r.mood_index, bed_time=r.bed_time,
        wake_time=r.wake_time, sleep_hours=r.sleep_hours, sleep_quality=r.sleep_quality,
        symptoms=json.loads(r.symptoms) if r.symptoms else None, source=r.source,
        created_at=_aware(r.created_at), updated_at=_aware(r.updated_at),
    )


def _find_checkin(db: Session, astronaut_id: str, day: dt.date) -> Checkin | None:
    return db.scalars(
        select(Checkin).where(Checkin.astronaut_id == astronaut_id, Checkin.date == day)
        .execution_options(populate_existing=True)
    ).one_or_none()


def get_checkin(db: Session, user: CurrentUser, day: dt.date) -> tuple[CheckinOut, str]:
    row = _find_checkin(db, user.astronaut_id, day) if user.astronaut_id else None
    if row is None:
        raise NotFound(str(day))
    return _checkin_out(row), etag_of(row.updated_at)


def put_checkin(db: Session, user: CurrentUser, day: dt.date, body: CheckinIn,
                if_match: str | None) -> tuple[CheckinOut, str, bool]:
    astro = _writer(db, user)
    values = dict(
        mission_day=_day(astro, day), mood=body.mood, energy=body.energy, stress=body.stress,
        loneliness=body.loneliness, crew=body.crew, mood_index=body.mood_index,
        bed_time=body.bed_time, wake_time=body.wake_time,
        sleep_hours=sleep_hours_between(body.bed_time, body.wake_time),
        sleep_quality=body.sleep_quality, symptoms=to_json(body.symptoms), source="manual",
    )
    row = _find_checkin(db, astro.astronaut_id, day)
    if row is None:
        if if_match not in (None, "*"):
            raise PreconditionFailed("Kayıt yok; If-Match gönderilmemeli")
        try:
            with db.begin_nested():
                db.add(Checkin(date=day, astronaut_id=astro.astronaut_id, created_at=NOW,
                               updated_at=NOW, **values))
        except IntegrityError:
            raise PreconditionFailed("Aynı gün için kayıt az önce oluşturuldu") from None
        created = True
    else:
        # Güncelleme yalnız istemcinin gördüğü sürüm hâlâ güncelse yapılır.
        if if_match != etag_of(row.updated_at):
            raise PreconditionFailed("Check-in değişmiş; yeniden yükleyip tekrar deneyin")
        done = db.execute(
            update(Checkin).where(Checkin.id == row.id, Checkin.updated_at == row.updated_at)
            .values(updated_at=NOW, **values).execution_options(synchronize_session=False)
        ).rowcount
        if done != 1:
            raise PreconditionFailed("Check-in değişmiş; yeniden yükleyip tekrar deneyin")
        created = False
    db.commit()
    fresh = _find_checkin(db, astro.astronaut_id, day)
    return _checkin_out(fresh), etag_of(fresh.updated_at), created


# --- Haftalık ölçek ----------------------------------------------------------------------


def create_weekly(db: Session, user: CurrentUser, body: WeeklyIn) -> tuple[WeeklyOut, bool]:
    astro = _writer(db, user)
    taken = _naive_ms(body.taken_at)
    wanted = dict(taken_at=taken, answers=body.answers, who5_score=body.who5_score,
                  phq2_score=body.phq2_score, gad2_score=body.gad2_score,
                  share_with_crew_medical=body.share_with_crew_medical)
    row = WeeklyAssessment(
        taken_at=taken, mission_day=_day(astro, taken.date()), answers=to_json(body.answers),
        who5_score=body.who5_score, phq2_score=body.phq2_score, gad2_score=body.gad2_score,
        share_with_crew_medical=body.share_with_crew_medical, source="manual",
        astronaut_id=astro.astronaut_id, client_request_id=body.client_request_id,
    )
    saved, created = _insert_or_replay(
        db, row,
        lambda: db.scalars(select(WeeklyAssessment).where(
            WeeklyAssessment.astronaut_id == astro.astronaut_id,
            WeeklyAssessment.client_request_id == body.client_request_id)).one_or_none(),
        wanted,
        lambda r: dict(taken_at=r.taken_at, answers=json.loads(r.answers),
                       who5_score=r.who5_score, phq2_score=r.phq2_score,
                       gad2_score=r.gad2_score, share_with_crew_medical=r.share_with_crew_medical),
    )
    db.commit()
    return WeeklyOut(id=saved.id, taken_at=_aware(saved.taken_at), mission_day=saved.mission_day,
                     who5_score=saved.who5_score, phq2_score=saved.phq2_score,
                     gad2_score=saved.gad2_score,
                     share_with_crew_medical=saved.share_with_crew_medical), created


# --- Bilişsel test -------------------------------------------------------------------------

_COG_FIELDS = ("test_type", "duration_s", "n_trials", "mean_rt_ms", "median_rt_ms", "speed",
               "lapses", "false_starts", "accuracy", "correct_count", "valid", "invalid_reason",
               "device")


def create_cognitive(db: Session, user: CurrentUser, body: CognitiveIn) -> tuple[CognitiveOut, bool]:
    astro = _writer(db, user)
    taken = _naive_ms(body.taken_at)
    fields = {f: getattr(body, f) for f in _COG_FIELDS}
    wanted = dict(fields, taken_at=taken, raw=body.raw)
    row = CognitiveTest(taken_at=taken, mission_day=_day(astro, taken.date()),
                        raw=to_json(body.raw), source="manual", astronaut_id=astro.astronaut_id,
                        client_request_id=body.client_request_id, **fields)
    saved, created = _insert_or_replay(
        db, row,
        lambda: db.scalars(select(CognitiveTest).where(
            CognitiveTest.astronaut_id == astro.astronaut_id,
            CognitiveTest.client_request_id == body.client_request_id)).one_or_none(),
        wanted,
        lambda r: dict({f: getattr(r, f) for f in _COG_FIELDS}, taken_at=r.taken_at,
                       raw=json.loads(r.raw)),
    )
    db.commit()
    return CognitiveOut(id=saved.id, taken_at=_aware(saved.taken_at), mission_day=saved.mission_day,
                        test_type=saved.test_type, valid=saved.valid), created


# --- Fizyolojik ölçüm ------------------------------------------------------------------------


def create_physiological(db: Session, user: CurrentUser,
                         body: PhysiologicalIn) -> PhysiologicalOut:
    astro = _writer(db, user)
    d = db.get(MeasurementDefinition, body.measurement)
    if d is None or d.module != "physiological":
        raise ValidationFailed(f"'{body.measurement}' sözlükte fizyolojik ölçüm olarak tanımlı değil")
    if d.canonical_unit != body.unit:
        raise ValidationFailed(f"'{body.measurement}' birimi {d.canonical_unit} olmalı")
    measured_at = _naive_ms(body.measured_at) if body.measured_at else None
    values = dict(
        measurement_code=body.measurement, eye_code="NA",
        value_num=body.value_num, value_text=body.value_text, valid=body.valid,
        quality_score=body.quality_score, metadata_json=to_json(body.metadata_json),
        measured_date=body.measured_date, measured_at=measured_at,
        time_precision="timestamp" if measured_at else "date",
        mission_day=_day(astro, body.measured_date), source="manual",
    )
    wanted = {k: v for k, v in values.items() if k != "metadata_json"} | {
        "metadata_json": body.metadata_json}

    def as_dict(r: MeasurementRecord) -> dict[str, Any]:
        out = {k: getattr(r, k) for k in values if k != "metadata_json"}
        out["metadata_json"] = json.loads(r.metadata_json) if r.metadata_json else None
        if out["value_num"] is not None:
            out["value_num"] = Decimal(out["value_num"]).normalize()
        return out

    if wanted["value_num"] is not None:
        wanted["value_num"] = Decimal(wanted["value_num"]).normalize()
    row = MeasurementRecord(record_id=uuid.uuid4(), astronaut_id=astro.astronaut_id,
                            client_request_id=body.client_request_id, **values)
    saved, created = _insert_or_replay(
        db, row,
        lambda: db.scalars(select(MeasurementRecord).where(
            MeasurementRecord.astronaut_id == astro.astronaut_id,
            MeasurementRecord.client_request_id == body.client_request_id)).one_or_none(),
        wanted, as_dict,
    )
    db.commit()
    return PhysiologicalOut(record_id=saved.record_id, measurement=saved.measurement_code,
                            measured_date=saved.measured_date, mission_day=saved.mission_day,
                            created=created)


# --- Göz oturumu ------------------------------------------------------------------------------


def session_id_for(astronaut_id: str, flight_day: int) -> str:
    """S-A007-D074, uçuş öncesi S-A007-M060."""
    return f"S-{astronaut_id}-{'M' if flight_day < 0 else 'D'}{abs(flight_day):03d}"


def _eye_dict(tests) -> set[tuple]:
    return {(t["eye"], t["test"], Decimal(t["value"]).normalize(), t["unit"],
             json.dumps(t["amsler_cells"]) if t["amsler_cells"] is not None else None,
             t["n_correct"], t["n_presented"],
             Decimal(t["duration_s"]).normalize() if t["duration_s"] is not None else None)
            for t in tests}


def create_eye_session(db: Session, user: CurrentUser,
                       body: EyeSessionIn) -> tuple[EyeSessionOut, bool]:
    astro = _writer(db, user)
    sid = session_id_for(astro.astronaut_id, body.flight_day)
    if body.retest_of is not None:
        prev = db.get(Oturum, body.retest_of)
        if prev is None or prev.astronaut_id != astro.astronaut_id:
            raise ValidationFailed("retest_of bu astronotun mevcut bir oturumu olmalı")
        if prev.flight_day >= body.flight_day:
            raise ValidationFailed("Tekrar test önceki oturumdan sonraki bir günde olmalı")
    tests = [t.model_dump() for t in body.tests]
    session_values = dict(flight_day=body.flight_day, is_retest=body.retest_of is not None,
                          retest_of=body.retest_of,
                          quality_score=Decimal(body.quality_score).normalize(),
                          checklist=body.checklist)

    existing = db.get(Oturum, sid)
    if existing is not None:
        stored_tests = [dict(eye=k.eye.strip(), test=k.test, value=k.value, unit=k.unit,
                             amsler_cells=json.loads(k.amsler_cells) if k.amsler_cells else None,
                             n_correct=k.n_correct, n_presented=k.n_presented,
                             duration_s=k.duration_s)
                        for k in db.scalars(select(TestKaydi).where(TestKaydi.session_id == sid))]
        stored = dict(flight_day=existing.flight_day, is_retest=existing.is_retest,
                      retest_of=existing.retest_of,
                      quality_score=Decimal(existing.quality_score).normalize(),
                      checklist=json.loads(existing.checklist_json) if existing.checklist_json else None)
        if stored != session_values or _eye_dict(stored_tests) != _eye_dict(tests):
            raise IdempotencyConflict(f"{sid} zaten farklı içerikle kayıtlı")
        return EyeSessionOut(session_id=sid, flight_day=existing.flight_day,
                             is_retest=existing.is_retest, retest_of=existing.retest_of,
                             quality_score=existing.quality_score,
                             test_count=len(stored_tests)), False

    try:
        with db.begin_nested():
            db.add(Oturum(session_id=sid, astronaut_id=astro.astronaut_id,
                          date=astro.mission.start_date + dt.timedelta(days=body.flight_day),
                          flight_day=body.flight_day, is_retest=body.retest_of is not None,
                          retest_of=body.retest_of, quality_score=body.quality_score,
                          checklist_json=to_json(body.checklist), source="test_screen"))
            db.flush()
            for t in body.tests:
                db.add(TestKaydi(session_id=sid, astronaut_id=astro.astronaut_id,
                                 flight_day=body.flight_day, eye=t.eye.value, test=t.test,
                                 value=t.value, unit=t.unit,
                                 amsler_cells=to_json(t.amsler_cells), n_correct=t.n_correct,
                                 n_presented=t.n_presented, duration_s=t.duration_s))
    except IntegrityError:
        raise IdempotencyConflict(f"{sid} aynı anda başka istekle oluşturuldu") from None
    db.commit()
    return EyeSessionOut(session_id=sid, flight_day=body.flight_day,
                         is_retest=body.retest_of is not None, retest_of=body.retest_of,
                         quality_score=body.quality_score, test_count=len(body.tests)), True


# --- Baş ağrısı ---------------------------------------------------------------------------------


def record_headache(db: Session, user: CurrentUser, body: HeadacheIn) -> tuple[HeadacheOut, bool]:
    astro = _writer(db, user)
    row = Semptom(astronaut_id=astro.astronaut_id, flight_day=body.flight_day,
                  headache=body.headache)
    saved, created = _insert_or_replay(
        db, row, lambda: db.get(Semptom, (astro.astronaut_id, body.flight_day)),
        {"headache": body.headache}, lambda r: {"headache": r.headache},
    )
    db.commit()
    return HeadacheOut(flight_day=saved.flight_day, headache=saved.headache), created
