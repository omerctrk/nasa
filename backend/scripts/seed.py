"""A6: tekrar çalıştırılabilir seed (şema v5.0 §1, iş bölümü A6).

Ne ekler:
- anomaly.MeasurementDefinitions: VIEW'ın kullandığı davranış kodları (göz/SANS kapatıldı)
- core.Missions: M01 (gün 0 = 2027-01-05)
- core.Astronauts: A007 (aktif) + bir gösterim profili (is_display_only=1)
- core.Users: bir ASTRONAUT (A007) ve bir GROUND_CONTROL hesabı (Argon2 hash)

Kurallar:
- Tekrar çalıştırılınca çift kayıt oluşmaz. Var olan görev/astronot/hesap DEĞİŞTİRİLMEZ
  (A007 profil değerlerini yalnız A9 JSON import'u günceller; parola yalnız
  --reset-passwords ile değişir). Sözlük satırları koddaki tanıma eşitlenir.
- Parolalar repoya yazılmaz: SEED_ASTRONAUT_PASSWORD / SEED_GROUND_PASSWORD ortamdan gelir.
- Göz verisi, sentetik geçmiş ve evaluation verisi seed EDİLMEZ (A8/A9).
- astra_app hesabıyla çalışır (core ve sözlükte INSERT/UPDATE izni var; DELETE yok).

Çalıştırma (proje kökünden, migrate sonrası):
    docker compose run --rm seed
    docker compose run --rm seed python -m scripts.seed --reset-passwords
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.passwords import hash_password
from app.models import Astronaut, MeasurementDefinition, Mission, User
from app.repositories.sqlalchemy_identity import normalize_email

PROTOCOL_VERSION = "astra-v1"

# --- KESİN (belgelerde tanımlı) --------------------------------------------------
MISSION_ID = "M01"
MISSION_DAY0 = date(2027, 1, 5)
ACTIVE_ASTRONAUT_ID = "A007"

# (kod, modül, kanonik birim, değer türü, kötüleşme yönü)
# Göz kodları (near_acuity/contrast/amsler) SANS modülüyle birlikte kaldırıldı (takım kararı).
# Davranış: birimler şema aralıklarından; puan yönleri
# teyit edilmediği için "unconfirmed" (şema: teyitsiz yön varsayılmaz).
DEFINITIONS: tuple[tuple[str, str, str, str, str], ...] = (
    ("mood", "behavioral", "score_0_10", "integer", "unconfirmed"),
    ("energy", "behavioral", "score_0_10", "integer", "unconfirmed"),
    ("stress", "behavioral", "score_0_10", "integer", "unconfirmed"),
    ("loneliness", "behavioral", "score_0_4", "integer", "unconfirmed"),
    ("crew", "behavioral", "score_0_4", "integer", "unconfirmed"),
    ("mood_index", "behavioral", "score_0_100", "numeric", "unconfirmed"),
    ("sleep_hours", "behavioral", "h", "numeric", "unconfirmed"),
    ("sleep_quality", "behavioral", "score_1_5", "integer", "unconfirmed"),
    ("pvt_mean_rt", "behavioral", "ms", "numeric", "unconfirmed"),
    ("pvt_median_rt", "behavioral", "ms", "numeric", "unconfirmed"),
    ("pvt_lapses", "behavioral", "count", "integer", "unconfirmed"),
    ("pvt_false_starts", "behavioral", "count", "integer", "unconfirmed"),
    ("rotation_mean_rt", "behavioral", "ms", "numeric", "unconfirmed"),
    ("rotation_accuracy", "behavioral", "ratio_0_1", "numeric", "unconfirmed"),
    ("dsst_accuracy", "behavioral", "ratio_0_1", "numeric", "unconfirmed"),
    ("dsst_correct_count", "behavioral", "count", "integer", "unconfirmed"),
)

# Fizyolojik kodlar: Ömer'in backend/config/history-policy.json'undaki "definition_confirmed"
# tanımlarla AYNI kod/birim/protokol (tests/unit/test_a6.py eşitliği denetler). Protokol farklı
# olursa geçmiş hazırlığı bu ölçümleri görmez. Kötüleşme yönü teyit edilmedi.
PHYSIOLOGICAL_PROTOCOL = "module-v2"
PHYSIOLOGICAL_DEFINITIONS: tuple[tuple[str, str, str, str, str], ...] = (
    ("heart_rate", "physiological", "BPM", "numeric", "unconfirmed"),
    ("systolic_bp", "physiological", "mmHg", "numeric", "unconfirmed"),
    ("diastolic_bp", "physiological", "mmHg", "numeric", "unconfirmed"),
    ("blood_glucose", "physiological", "mg/dL", "numeric", "unconfirmed"),
    ("body_temperature", "physiological", "°C", "numeric", "unconfirmed"),
    # Sentetik demo kaynakları (ekip kararı, 15 Kasım): pulse oksimetre, tonometre, kişisel
    # dozimetre ve astronotun bulunduğu modülün kabin CO₂ sensörü. Astronota bağlı kaydedilir.
    ("spo2", "physiological", "%", "numeric", "unconfirmed"),
    ("intraocular_pressure", "physiological", "mmHg", "numeric", "unconfirmed"),
    ("radiation_dose", "physiological", "mSv/d", "numeric", "unconfirmed"),
    ("cabin_co2", "physiological", "mmHg", "numeric", "unconfirmed"),
)

# --- GEÇİCİ (belgelerde yok; ekip teyidi bekliyor) ---------------------------------
MISSION_NAME = "M01"  # TODO(ekip): görev adı
MISSION_SCENARIO = "ISS"  # SANS params: ISS kabin CO₂ kalibrasyonu
MISSION_LENGTH_DAYS = 182  # SANS params.yaml: flight_days 182 [V]
DISPLAY_ASTRONAUT_ID = "A008"  # TODO(ekip): ikinci (yalnız gösterim) profil kimliği
ASTRONAUT_EMAIL = "astronaut@astra.local"  # TODO(ekip): demo giriş adresleri
GROUND_EMAIL = "kule@astra.local"


@dataclass
class SeedReport:
    created: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)

    def line(self) -> str:
        return (f"eklenen={len(self.created)} güncellenen={len(self.updated)} "
                f"değişmeyen={len(self.unchanged)}")


def _definitions(db: Session, report: SeedReport) -> None:
    existing = {d.measurement_code: d for d in db.scalars(select(MeasurementDefinition))}
    rows = [(*d, PROTOCOL_VERSION) for d in DEFINITIONS] + [
        (*d, PHYSIOLOGICAL_PROTOCOL) for d in PHYSIOLOGICAL_DEFINITIONS]
    for code, module, unit, kind, direction, protocol in rows:
        want = dict(module=module, canonical_unit=unit, value_kind=kind,
                    protocol_version=protocol, worsening_direction=direction)
        row = existing.get(code)
        if row is None:
            db.add(MeasurementDefinition(measurement_code=code, **want))
            report.created.append(f"definition:{code}")
        elif any(getattr(row, k) != v for k, v in want.items()):
            for k, v in want.items():
                setattr(row, k, v)
            report.updated.append(f"definition:{code}")
        else:
            report.unchanged.append(f"definition:{code}")


def _mission(db: Session, report: SeedReport) -> None:
    if db.get(Mission, MISSION_ID) is None:
        db.add(Mission(mission_id=MISSION_ID, name=MISSION_NAME, start_date=MISSION_DAY0,
                       length_days=MISSION_LENGTH_DAYS, scenario=MISSION_SCENARIO))
        report.created.append(f"mission:{MISSION_ID}")
    else:
        report.unchanged.append(f"mission:{MISSION_ID}")


def _astronauts(db: Session, report: SeedReport) -> None:
    for astronaut_id, display_only in ((ACTIVE_ASTRONAUT_ID, False), (DISPLAY_ASTRONAUT_ID, True)):
        row = db.get(Astronaut, astronaut_id)
        if row is None:
            # SANS profil alanları (yaş, kilo, genler…) boş kalır: A9 JSON import doldurur.
            db.add(Astronaut(astronaut_id=astronaut_id, display_name=astronaut_id,
                             mission_id=MISSION_ID, is_display_only=display_only))
            report.created.append(f"astronaut:{astronaut_id}")
        elif row.is_display_only != display_only or row.mission_id != MISSION_ID:
            raise SystemExit(
                f"{astronaut_id} DB'de farklı tanımlı (görev={row.mission_id}, "
                f"gösterim={row.is_display_only}); seed sessizce değiştirmez."
            )
        else:
            report.unchanged.append(f"astronaut:{astronaut_id}")


def _users(db: Session, report: SeedReport, astronaut_pw: str, ground_pw: str,
           reset_passwords: bool) -> None:
    accounts = (
        (normalize_email(ASTRONAUT_EMAIL), "ASTRONAUT", ACTIVE_ASTRONAUT_ID, astronaut_pw),
        (normalize_email(GROUND_EMAIL), "GROUND_CONTROL", None, ground_pw),
    )
    for email, role, astronaut_id, password in accounts:
        row = db.scalars(select(User).where(User.email == email)).one_or_none()
        if row is None:
            db.add(User(email=email, password_hash=hash_password(password), role=role,
                        astronaut_id=astronaut_id))
            report.created.append(f"user:{email}")
            continue
        if row.role != role or row.astronaut_id != astronaut_id:
            raise SystemExit(f"{email} DB'de farklı rol/astronotla kayıtlı; seed değiştirmez.")
        if reset_passwords:
            row.password_hash = hash_password(password)
            report.updated.append(f"user:{email} (parola)")
        else:
            report.unchanged.append(f"user:{email}")


def run_seed(db: Session, astronaut_pw: str, ground_pw: str,
             reset_passwords: bool = False) -> SeedReport:
    """Tek transaction'da çalışır; commit çağıran tarafındadır."""
    if not astronaut_pw or not ground_pw:
        raise SystemExit("SEED_ASTRONAUT_PASSWORD ve SEED_GROUND_PASSWORD ayarlanmalı.")
    report = SeedReport()
    _definitions(db, report)
    _mission(db, report)
    db.flush()  # astronot FK'si için görev önce
    _astronauts(db, report)
    db.flush()
    _users(db, report, astronaut_pw, ground_pw, reset_passwords)
    db.flush()
    return report


def main(argv: list[str]) -> int:
    from app.db.session import SessionLocal

    reset = "--reset-passwords" in argv
    with SessionLocal() as db:
        try:
            report = run_seed(db, os.environ.get("SEED_ASTRONAUT_PASSWORD", ""),
                              os.environ.get("SEED_GROUND_PASSWORD", ""), reset)
            db.commit()
        except BaseException:
            db.rollback()  # kısmi seed bırakılmaz
            raise
    print("Seed tamam:", report.line())
    for item in report.created + report.updated:
        print("  +", item)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
