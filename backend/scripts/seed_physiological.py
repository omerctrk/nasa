"""Fill missing daily physiological demo measurements without replacing history.

Example: python -m scripts.seed_physiological --end-date 2026-11-15 --apply
Without --apply, only report proposed counts. Values are demo scenarios, not
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
from scripts.seed import PHYSIOLOGICAL_DEFINITIONS, PHYSIOLOGICAL_PROTOCOL

GENERATOR = "physiological-demo-v1"
# mean, bounded daily variation, late-mission demo increase (not clinical limits)
PARAMETERS = {
    "heart_rate": (72, 3, 14),
    "systolic_bp": (118, 4, 18),
    "diastolic_bp": (77, 3, 12),
    "blood_glucose": (94, 5, 24),
    "body_temperature": (36.65, 0.15, 0.7),
}


def sample(astronaut_id: str, day: date, mission_day: int, code: str) -> Decimal:
    rng = random.Random(f"{GENERATOR}:{astronaut_id}:{day}:{code}")
    mean, variation, increase = PARAMETERS[code]
    drift = min(1, max(0, (mission_day - 60) / 14))
    return Decimal(str(round(mean + rng.uniform(-variation, variation) + increase * drift, 2)))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--astronaut", default="A007")
    parser.add_argument("--end-date", type=date.fromisoformat, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    engine = create_engine(get_settings().database_url)
    with Session(engine) as db, db.begin():
        astronaut = db.get(Astronaut, args.astronaut)
        if astronaut is None or astronaut.is_display_only:
            raise SystemExit("An active, non-display astronaut is required.")
        mission = db.get(Mission, astronaut.mission_id)
        start = mission.start_date + timedelta(days=1)
        if not start <= args.end_date < mission.start_date + timedelta(days=mission.length_days):
            raise SystemExit("End date must be within the mission.")
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
