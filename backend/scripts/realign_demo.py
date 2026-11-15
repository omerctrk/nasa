"""Demo takvimini bugüne hizalar: senaryonun son günü (görev günü 74) = bugün (UTC).

Neden: demo verisi görev günü 1–74'tür. Takvim bir kez kurulup günler geçtikçe "bugün"
75, 76… olur ve panel boş bir günle açılır. Bu araç görev başlangıcını ve görevdeki
astronotların TÜM tarihli kayıtlarını aynı gün sayısı kadar kaydırır:

    tarih − görev başlangıcı = görev günü   (mission_day değişmez, ilişki korunur)

Kaydırılanlar: core.Missions.start_date · behavioral.checkins.date ·
behavioral.cognitive_tests.taken_at · behavioral.weekly_assessments.taken_at ·
anomaly.MeasurementRecords.measured_date/measured_at.
Kaydırılmayanlar: gerçek olay zamanları (created_at/updated_at, analiz işleri, sonuçlar,
alarmlar, bildirimler). Bunlar demoda gerçekten olanlardır.

Güvenlik:
- Varsayılan KURU çalışmadır; yalnız --apply ile yazar. Tek transaction: ya hepsi ya hiçbiri.
- Senaryo sonrasına (görev günü > 74) ait kayıt varsa durur: hizalama o kaydı geleceğe atardı.
- Tarihi görev günüyle tutmayan kayıt varsa durur (önceden bozulmuş veri büyütülmez).
- Her tablo TEK UPDATE ile kayar (DATEADD); UNIQUE(astronot, gün) ara adımda çakışmaz.

Ölçüm/test tabloları uygulama hesabına yalnız-ekleme açıktır; bu yüzden migrate (sa)
servisiyle çalışır:
    docker compose run --rm migrate python -m scripts.realign_demo            # rapor
    docker compose run --rm migrate python -m scripts.realign_demo --apply    # uygula
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys

from sqlalchemy import func, literal_column, select, update
from sqlalchemy.orm import Session

from app.models import Astronaut, Mission
from app.models.behavioral import Checkin, CognitiveTest, WeeklyAssessment
from app.models.measurements import MeasurementRecord

MISSION_ID = "M01"
LAST_DAY = 74  # scripts/demo_data.py: senaryonun son görev günü

# (ad, model, astronot kolonu, kaydırılan kolonlar, görev günüyle karşılaştırılan tarih kolonu)
TABLES = (
    ("behavioral.checkins", Checkin, Checkin.astronaut_id, (Checkin.date,), Checkin.date),
    ("behavioral.cognitive_tests", CognitiveTest, CognitiveTest.astronaut_id,
     (CognitiveTest.taken_at,), None),
    ("behavioral.weekly_assessments", WeeklyAssessment, WeeklyAssessment.astronaut_id,
     (WeeklyAssessment.taken_at,), None),
    ("anomaly.MeasurementRecords", MeasurementRecord, MeasurementRecord.astronaut_id,
     (MeasurementRecord.measured_date, MeasurementRecord.measured_at), MeasurementRecord.measured_date),
)


class RealignRefused(SystemExit):
    pass


def shift_days(start: dt.date, today: dt.date, last_day: int = LAST_DAY) -> int:
    """Son senaryo günü bugüne denk gelsin diye kaç gün kaydırılacağı (geri için negatif)."""
    return (today - dt.timedelta(days=last_day) - start).days


def shift_statement(model, astronaut_col, columns, astronaut_ids, delta: int):
    """Tek UPDATE: her kolon DATEADD(day, delta, kolon). NULL kalır (DATEADD(NULL)=NULL)."""
    values = {col.key: func.dateadd(literal_column("day"), delta, col) for col in columns}
    return (update(model).where(astronaut_col.in_(astronaut_ids)).values(**values)
            .execution_options(synchronize_session=False))


def realign(db: Session, today: dt.date, apply: bool = False) -> dict:
    mission = db.get(Mission, MISSION_ID)
    if mission is None:
        raise RealignRefused(f"{MISSION_ID} yok: önce seed çalıştırın.")
    ids = list(db.scalars(select(Astronaut.astronaut_id).where(Astronaut.mission_id == MISSION_ID)))
    delta = shift_days(mission.start_date, today)
    report = {"mode": "applied" if apply else "dry_run", "today": today.isoformat(),
              "start_before": mission.start_date.isoformat(), "shift_days": delta, "tables": {}}

    beyond, broken = {}, {}
    for name, model, astro, _cols, date_col in TABLES:
        mission_day = model.mission_day
        count = db.scalar(select(func.count()).select_from(model).where(astro.in_(ids))) or 0
        report["tables"][name] = count
        late = db.scalar(select(func.count()).select_from(model)
                         .where(astro.in_(ids), mission_day > LAST_DAY)) or 0
        if late:
            beyond[name] = late
        if date_col is not None:
            bad = db.scalar(select(func.count()).select_from(model).where(
                astro.in_(ids), mission_day.is_not(None),
                func.datediff(literal_column("day"), mission.start_date, date_col) != mission_day)) or 0
            if bad:
                broken[name] = bad
    if beyond:
        raise RealignRefused(
            f"Görev günü {LAST_DAY}'ten sonraki kayıtlar var {beyond}: hizalama bunları geleceğe "
            "atardı. Demo veritabanını sıfırlayın (docker compose down -v) veya kayıtları inceleyin.")
    if broken:
        raise RealignRefused(f"Tarihi görev günüyle tutmayan kayıtlar var {broken}; hizalama durdu.")
    if delta == 0:
        report["mode"] = "already_aligned"
        report["start_after"] = report["start_before"]
        return report

    for _name, model, astro, cols, _date_col in TABLES:
        db.execute(shift_statement(model, astro, cols, ids, delta))
    mission.start_date = mission.start_date + dt.timedelta(days=delta)
    db.flush()
    report["start_after"] = mission.start_date.isoformat()
    return report


def main(argv: list[str]) -> int:
    from app.db.session import SessionLocal

    parser = argparse.ArgumentParser(description="Demo takvimini bugüne hizalar (son gün = bugün).")
    parser.add_argument("--apply", action="store_true", help="değişiklikleri yaz (yoksa kuru çalışma)")
    args = parser.parse_args(argv)
    today = dt.datetime.now(dt.UTC).date()
    with SessionLocal() as db:
        try:
            report = realign(db, today, apply=args.apply)
            if args.apply and report["mode"] == "applied":
                db.commit()
            else:
                db.rollback()
        except RealignRefused as exc:
            db.rollback()
            print(json.dumps({"mode": "refused", "reason": str(exc)}, ensure_ascii=False))
            return 3
        except BaseException:
            db.rollback()
            raise
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
