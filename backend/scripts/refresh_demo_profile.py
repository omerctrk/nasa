"""Profili değişen demo astronotunun ÜRETİLMİŞ verisini siler; üreticiler yenisini yazar.

Neden: seed_physiological ve demo_data yalnız EKSİK kayıtları ekler, var olana dokunmaz. Bir
astronotun senaryosu (PROFILES) değiştirilirse eski senaryonun kayıtları veritabanında kalır
ve yenisi hiç yüklenmez. Bu araç eskiyi fark eder ve temizler:

  - Fizyolojik: üretilmiş (source='synthetic') kayıtların metadata'sındaki "profile" etiketi
    seed_physiological.PROFILE_TAGS ile aynı değilse eski sayılır.
  - Davranış: üretilmiş (source='seed') bilişsel testlerin değeri bugünkü üreticinin çıktısıyla
    aynı değilse eski sayılır (testler eklenince değişmez; karşılaştırma güvenlidir).

Eskiyse o astronotun yalnız ÜRETİLMİŞ kayıtları silinir (synthetic / seed). Elle girilmiş
(manual) kayıtlara, analiz sonuçlarına, alarmlara ve bildirimlere dokunulmaz. Yalnız kendi
profili olan astronotlarda çalışır (PROFILE_TAGS); A007 bu araçla değiştirilemez.

Uygulama hesabının DELETE izni yoktur; bu yüzden migrate (sa) servisiyle çalışır. Ardından
demo_data ve seed_physiological çalıştırılmalıdır (baslat.ps1 sırayla yapar):
    docker compose run --rm migrate python -m scripts.refresh_demo_profile --astronaut A009          # rapor
    docker compose run --rm migrate python -m scripts.refresh_demo_profile --astronaut A009 --apply  # uygula
"""
from __future__ import annotations

import argparse
import json
import sys
import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models.behavioral import Checkin, CognitiveTest, WeeklyAssessment
from app.models.identity import Astronaut
from app.models.measurements import MeasurementRecord
from scripts.seed_behavioral import generate
from scripts.seed_physiological import PROFILE_TAGS

BEHAVIORAL = (Checkin, CognitiveTest, WeeklyAssessment)


def _same(a, b) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return abs(float(a) - float(b)) < 1e-6


def physiological_stale(db: Session, astronaut_id: str) -> bool:
    rows = db.scalars(select(MeasurementRecord.metadata_json).where(
        MeasurementRecord.astronaut_id == astronaut_id, MeasurementRecord.source == "synthetic"))
    want = PROFILE_TAGS[astronaut_id]
    for raw in rows:
        try:
            tag = json.loads(raw or "{}").get("profile")
        except (TypeError, ValueError):
            tag = None
        if tag != want:
            return True
    return False


def behavioral_stale(db: Session, astronaut_id: str) -> bool:
    expected = {uuid.UUID(r["client_request_id"]): r for r in generate(astronaut_id)["cognitive_tests"]}
    rows = db.execute(select(CognitiveTest.client_request_id, CognitiveTest.mean_rt_ms,
                             CognitiveTest.accuracy, CognitiveTest.lapses).where(
        CognitiveTest.astronaut_id == astronaut_id, CognitiveTest.source == "seed")).all()
    for request_id, mean_rt, accuracy, lapses in rows:
        want = expected.get(request_id)
        if want is None or not (_same(mean_rt, want["mean_rt_ms"]) and _same(accuracy, want["accuracy"])
                                and _same(lapses, want["lapses"])):
            return True
    return False


def refresh(db: Session, astronaut_id: str) -> dict:
    if astronaut_id not in PROFILE_TAGS:
        raise SystemExit(f"{astronaut_id} için ayrı profil yok (PROFILE_TAGS); bu araç onu değiştirmez.")
    report: dict = {"astronaut": astronaut_id, "profile": PROFILE_TAGS[astronaut_id], "deleted": {}}
    if db.get(Astronaut, astronaut_id) is None:
        return report | {"status": "astronaut_missing"}  # henüz seed edilmemiş: silinecek bir şey yok
    stale = {"physiological": physiological_stale(db, astronaut_id),
             "behavioral": behavioral_stale(db, astronaut_id)}
    report["stale"] = stale
    if stale["physiological"]:
        result = db.execute(delete(MeasurementRecord).where(
            MeasurementRecord.astronaut_id == astronaut_id, MeasurementRecord.source == "synthetic",
        ).execution_options(synchronize_session=False))
        report["deleted"]["anomaly.MeasurementRecords"] = result.rowcount
    if stale["behavioral"]:
        for model in BEHAVIORAL:
            result = db.execute(delete(model).where(
                model.astronaut_id == astronaut_id, model.source == "seed",
            ).execution_options(synchronize_session=False))
            report["deleted"][model.__table__.fullname] = result.rowcount
    report["status"] = "stale" if any(stale.values()) else "up_to_date"
    report["manual_rows_kept"] = {
        "anomaly.MeasurementRecords": db.scalar(select(func.count()).select_from(MeasurementRecord).where(
            MeasurementRecord.astronaut_id == astronaut_id, MeasurementRecord.source == "manual")) or 0,
        "behavioral.checkins": db.scalar(select(func.count()).select_from(Checkin).where(
            Checkin.astronaut_id == astronaut_id, Checkin.source == "manual")) or 0,
    }
    return report


def main(argv: list[str]) -> int:
    from app.db.session import SessionLocal

    parser = argparse.ArgumentParser(description="Profili değişen demo astronotunun üretilmiş verisini siler.")
    parser.add_argument("--astronaut", required=True)
    parser.add_argument("--apply", action="store_true", help="sil (yoksa kuru çalışma)")
    args = parser.parse_args(argv)
    with SessionLocal() as db:
        try:
            report = refresh(db, args.astronaut)
            report["mode"] = "applied" if args.apply else "dry_run"
            if args.apply and report["deleted"]:
                db.commit()
            else:
                db.rollback()
        except BaseException:
            db.rollback()
            raise
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
