"""Demo verisi (A8, davranış kısmı): Şule'nin 74 günlük senaryosunu veritabanına yükler.

Kaynak: scripts/seed_behavioral.py (Şule) — ilk 60 gün stabil, son 14 gün kademeli değişim.
Değerler DEMO amaçlıdır, klinik değildir; büyüklükler Şule'nin CONFIG'inde tek yerdedir.

Tarihler görev takvimine yerleştirilir: tarih = core.Missions.start_date (gün 0) + görev günü.

Bugüne hizalama (varsayılan): şemadaki gün 0 (2027-01-05) gelecekte olduğu için panel
"görev günü -51" gösterir ve son 30 günü boş bulur. Sunum için bu YEREL demo DB'sinde M01'in
başlangıcı bugün - 74 gün yapılır: senaryonun son günü (74) BUGÜN olur; panel, check-in ve
analiz 74. günü "bugün" görür (ekip kararı: referans gün 74). Sonraki günlerde takvimi yeniden
hizalamak için: scripts/realign_demo.py. Şemadaki tarihi korumak için: --sema-tarihi

- Yalnız davranış tabloları: behavioral.checkins / cognitive_tests / weekly_assessments.
  Fizyolojik ölçüm (nabız, tansiyon…) bu senaryoda YOK; uydurulmaz, ekipten gelecek.
- Tekrar çalıştırılabilir: aynı gün / aynı client_request_id varsa atlanır, üzerine yazılmaz.
- astra_app hesabıyla çalışır (seed servisi): docker compose run --rm seed python -m scripts.demo_data
"""
from __future__ import annotations

import datetime as dt
import json
import sys
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.behavioral import Checkin, CognitiveTest, WeeklyAssessment
from app.models.identity import Astronaut, Mission

ASTRONAUT_ID = "A007"


def _ts(value: str, shift: dt.timedelta) -> dt.datetime:
    """'...Z' zaman damgası → kaydırılmış, saat dilimsiz UTC (DATETIME2)."""
    t = dt.datetime.fromisoformat(value.replace("Z", "+00:00")) + shift
    return t.astimezone(dt.UTC).replace(tzinfo=None)


LAST_DAY = 74  # Şule'nin senaryosunun son görev günü

RESET_HINT = (
    "Eski demo verisi gelecek tarihte (2027) duruyor ve uygulama hesabı silemiyor.\n"
    "Yerel demo veritabanını sıfırlayın:\n"
    "  docker compose down -v\n"
    "  baslat.cmd (çift tık)  -> sonra yeni bir terminalde bu komutu tekrar çalıştırın"
)


def _align_to_today(db: Session, mission: Mission) -> None:
    """Senaryonun son günü bugün olacak şekilde M01 başlangıcını kaydırır (yalnız boş DB'de)."""
    today = dt.datetime.now(dt.UTC).date()
    has_rows = db.scalar(select(Checkin.id).where(Checkin.astronaut_id == ASTRONAUT_ID,
                                                  Checkin.source == "seed").limit(1)) is not None
    if not has_rows:
        mission.start_date = today - dt.timedelta(days=LAST_DAY)
        db.flush()
    elif mission.start_date + dt.timedelta(days=LAST_DAY) > today:  # senaryo gelecekte kalmış
        raise SystemExit(RESET_HINT)


def load(db: Session, align: bool = True) -> dict[str, int]:
    from scripts.seed_behavioral import CONFIG, generate

    astronaut = db.get(Astronaut, ASTRONAUT_ID)
    if astronaut is None:
        raise SystemExit("A007 yok: önce 'docker compose run --rm seed' çalıştırın.")
    mission = db.get(Mission, astronaut.mission_id)
    if align:
        _align_to_today(db, mission)
    data = generate()
    # Şule'nin günü 1 = CONFIG['mission_start']; bizde tarih = start_date + görev günü.
    shift = (mission.start_date + dt.timedelta(days=1)) - CONFIG["mission_start"]
    to_date = lambda day: mission.start_date + dt.timedelta(days=day)  # noqa: E731
    added = {"checkins": 0, "cognitive_tests": 0, "weekly_assessments": 0}

    have_days = set(db.scalars(select(Checkin.date).where(Checkin.astronaut_id == ASTRONAUT_ID)))
    for r in data["checkins"]:
        day = to_date(r["mission_day"])
        if day in have_days:
            continue
        db.add(Checkin(
            astronaut_id=ASTRONAUT_ID, date=day, mission_day=r["mission_day"],
            mood=r["mood"], energy=r["energy"], stress=r["stress"], loneliness=r["loneliness"],
            crew=r["crew_relation"], mood_index=r["mood_index"],
            bed_time=dt.time.fromisoformat(r["bed_time"]), wake_time=dt.time.fromisoformat(r["wake_time"]),
            sleep_hours=r["sleep_hours"], sleep_quality=r["sleep_quality"], symptoms=r["symptoms"],
            source="seed", created_at=_ts(r["created_at"], shift), updated_at=_ts(r["updated_at"], shift)))
        added["checkins"] += 1

    have_tests = set(db.scalars(select(CognitiveTest.client_request_id)
                                .where(CognitiveTest.astronaut_id == ASTRONAUT_ID)))
    for r in data["cognitive_tests"]:
        rid = uuid.UUID(r["client_request_id"])
        if rid in have_tests:
            continue
        db.add(CognitiveTest(
            astronaut_id=ASTRONAUT_ID, client_request_id=rid, taken_at=_ts(r["taken_at"], shift),
            mission_day=r["mission_day"], test_type=r["test_type"], duration_s=r["duration_s"],
            n_trials=r["n_trials"], mean_rt_ms=r["mean_rt_ms"], median_rt_ms=r["median_rt_ms"],
            speed=r["speed"], lapses=r["lapses"], false_starts=r["false_starts"],
            accuracy=r["accuracy"], correct_count=r["correct_count"], valid=r["valid"],
            invalid_reason=r["invalid_reason"], device=r["device"], raw=r["raw"], source="seed"))
        added["cognitive_tests"] += 1

    have_weekly = set(db.scalars(select(WeeklyAssessment.client_request_id)
                                 .where(WeeklyAssessment.astronaut_id == ASTRONAUT_ID)))
    for r in data["weekly_assessments"]:
        rid = uuid.UUID(r["client_request_id"])
        if rid in have_weekly:
            continue
        json.loads(r["answers"])  # bozuk JSON'u DB'ye göndermeden yakala
        db.add(WeeklyAssessment(
            astronaut_id=ASTRONAUT_ID, client_request_id=rid, taken_at=_ts(r["taken_at"], shift),
            mission_day=r["mission_day"], answers=r["answers"], who5_score=r["who5_score"],
            phq2_score=r["phq2_score"], gad2_score=r["gad2_score"],
            share_with_crew_medical=r["share_with_crew_medical"], source="seed"))
        added["weekly_assessments"] += 1
    db.flush()
    return added


def main(argv: list[str]) -> int:
    from app.db.session import SessionLocal

    with SessionLocal() as db:
        try:
            added = load(db, align="--sema-tarihi" not in argv)
            db.commit()
            start = db.get(Mission, db.get(Astronaut, ASTRONAUT_ID).mission_id).start_date
        except BaseException:
            db.rollback()  # yarım yükleme bırakılmaz
            raise
    print("Demo veri tamam:", ", ".join(f"{k}=+{v}" for k, v in added.items()))
    print(f"Görev günü 0: {start}  (senaryonun son günü: {start + dt.timedelta(days=LAST_DAY)})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
