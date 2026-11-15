"""Fill missing daily physiological demo measurements without replacing history.

Example: python -m scripts.seed_physiological --end-date <görev günü 74'ün tarihi> --apply
Without --apply, only report proposed counts. The end date may not pass mission day 74
(the demo scenario's last day = "today" after scripts/realign_demo.py); generated rows after
it would block calendar realignment. Use --beyond-scenario only on purpose. Values are demo scenarios, not
clinical reference ranges. Behavioral records remain in their own source tables.
"""
from __future__ import annotations

import argparse
import json
import random
import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Astronaut, MeasurementDefinition, MeasurementRecord, Mission
from scripts.demo_data import LAST_DAY
from scripts.seed import PHYSIOLOGICAL_DEFINITIONS, PHYSIOLOGICAL_PROTOCOL

GENERATOR = "physiological-demo-v1"
# mean, bounded daily variation, late-mission demo change (not clinical limits).
# Ranges for the 15 Nov additions follow published ISS values:
#  spo2                 normoxic cabin (~21 % O2, 1 atm): 96-99 %; slight late fall
#  intraocular_pressure early-flight elevation within normal (10-21 mmHg); late rise
#  radiation_dose       ISS LEO personal dose ~0.4-0.7 mSv/day; no trend
#  cabin_co2            ISS typical 2-3.5 mmHg; late rise toward the 4 mmHg operating limit
PARAMETERS = {
    "heart_rate": (72, 3, 14),
    "systolic_bp": (118, 4, 18),
    "diastolic_bp": (77, 3, 12),
    "blood_glucose": (94, 5, 24),
    "body_temperature": (36.65, 0.15, 0.7),
    "spo2": (97.6, 0.8, -1.6),
    "intraocular_pressure": (15.5, 1.2, 2.5),
    "radiation_dose": (0.55, 0.08, 0.0),
    "cabin_co2": (2.6, 0.3, 1.4),
}
# Device resolution: pulse oximeter reports whole %, tonometer 0.1 mmHg; others 2 decimals.
DECIMALS = {"spo2": 0, "intraocular_pressure": 1}


def sample(astronaut_id: str, day: date, mission_day: int, code: str) -> Decimal:
    rng = random.Random(f"{GENERATOR}:{astronaut_id}:{day}:{code}")
    mean, variation, increase = PARAMETERS[code]
    drift = min(1, max(0, (mission_day - 60) / 14))
    value = round(mean + rng.uniform(-variation, variation) + increase * drift, DECIMALS.get(code, 2))
    return Decimal(str(value))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--astronaut", default="A007")
    parser.add_argument("--end-date", type=date.fromisoformat, default=None,
                        help=f"default: mission day {LAST_DAY} (the demo scenario's last day)")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--beyond-scenario", action="store_true",
                        help=f"görev günü {LAST_DAY}'ten sonrasına da üret (takvim hizalamayı engeller)")
    args = parser.parse_args()
    engine = create_engine(get_settings().database_url)
    with Session(engine) as db, db.begin():
        astronaut = db.get(Astronaut, args.astronaut)
        if astronaut is None or astronaut.is_display_only:
            raise SystemExit("An active, non-display astronaut is required.")
        mission = db.get(Mission, astronaut.mission_id)
        start = mission.start_date + timedelta(days=1)
        if args.end_date is None:
            args.end_date = mission.start_date + timedelta(days=LAST_DAY)
        if not start <= args.end_date < mission.start_date + timedelta(days=mission.length_days):
            raise SystemExit("End date must be within the mission.")
        last = mission.start_date + timedelta(days=LAST_DAY)
        if args.end_date > last and not args.beyond_scenario:
            raise SystemExit(f"End date passes scenario day {LAST_DAY} ({last}); realign_demo would "
                             "refuse. Use that date, or --beyond-scenario on purpose.")
        for code, module, unit, kind, direction in PHYSIOLOGICAL_DEFINITIONS:
            definition = db.get(MeasurementDefinition, code)
            expected = dict(module=module, canonical_unit=unit, value_kind=kind,
                            protocol_version=PHYSIOLOGICAL_PROTOCOL)
            if definition is None:
                db.add(MeasurementDefinition(measurement_code=code,
                       worsening_direction=direction, **expected))
            elif any(getattr(definition, key) != value for key, value in expected.items()):
                raise SystemExit(f"Definition mismatch: {code}; review before generating.")
        db.flush()
        existing = set(db.execute(select(MeasurementRecord.measured_date,
                                         MeasurementRecord.measurement_code).where(
            MeasurementRecord.astronaut_id == args.astronaut,
            MeasurementRecord.measured_date.between(start, args.end_date),
        )).all())
        added = skipped = 0
        for offset in range((args.end_date - start).days + 1):
            day = start + timedelta(days=offset)
            mission_day = (day - mission.start_date).days
            for code in PARAMETERS:
                if (day, code) in existing:
                    skipped += 1
                    continue
                key = f"{GENERATOR}:{args.astronaut}:{day}:{code}"
                db.add(MeasurementRecord(
                    record_id=uuid.uuid5(uuid.NAMESPACE_URL, key + ':record'),
                    client_request_id=uuid.uuid5(uuid.NAMESPACE_URL, key + ':request'),
                    astronaut_id=args.astronaut, measurement_code=code, eye_code="NA",
                    value_num=sample(args.astronaut, day, mission_day, code), value_text=None,
                    valid=True, quality_score=Decimal("0.98"), source="synthetic",
                    measured_date=day, measured_at=None, time_precision="date",
                    mission_day=mission_day, metadata_json=json.dumps({
                        "generator": GENERATOR, "demo_only": True,
                        "scenario": "stable" if mission_day <= 60 else "gradual_demo_increase",
                        "protocol_version": PHYSIOLOGICAL_PROTOCOL,
                        "quality_score_note": "Simulated quality; not a sensor assessment",
                    }),
                ))
                added += 1
        db.flush()  # validate DB constraints even during a dry run
        if not args.apply:
            db.rollback()
        print(json.dumps({"mode": "applied" if args.apply else "dry_run",
                          "astronaut": args.astronaut, "start": str(start),
                          "end": str(args.end_date), "added": added, "skipped": skipped}))


if __name__ == "__main__":
    main()
