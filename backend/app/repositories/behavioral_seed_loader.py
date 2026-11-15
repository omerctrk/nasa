"""Seed çıktısını (scripts/seed_behavioral.py) bellek içi repository'lere yükler. Yalnız geliştirme / demo.

Seed satırları tablo biçimindedir (JSON metin alanları, taken_at + duration_s); burada
repository kayıtlarına çevrilir. id'leri repository atar.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

from app.repositories.behavioral import (
    CheckinRecord, CheckinRepository, CognitiveTestRecord, CognitiveTestRepository,
    WeeklyRecord, WeeklyRepository,
)

SEED_FILES = ("checkins", "cognitive_tests", "weekly_assessments")


def _ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def load_seed_rows(data: dict[str, list[dict]], checkin_repo: CheckinRepository,
                   test_repo: CognitiveTestRepository, weekly_repo: WeeklyRepository) -> dict[str, int]:
    for r in data["checkins"]:
        checkin_repo.add(CheckinRecord(
            id=None, astronaut_id=r["astronaut_id"], date=date.fromisoformat(r["date"]),
            mission_day=r["mission_day"], mood=r["mood"], energy=r["energy"], stress=r["stress"],
            loneliness=r["loneliness"], crew_relation=r["crew_relation"],
            bed_time=r["bed_time"], wake_time=r["wake_time"], sleep_quality=r["sleep_quality"],
            symptoms=json.loads(r["symptoms"]), mood_index=r["mood_index"], sleep_hours=r["sleep_hours"],
            source=r["source"], version=1, created_at=_ts(r["created_at"]), updated_at=_ts(r["updated_at"]),
        ))
    for r in data["cognitive_tests"]:
        started = _ts(r["taken_at"])
        test_repo.add(CognitiveTestRecord(
            id=None, astronaut_id=r["astronaut_id"], client_request_id=UUID(r["client_request_id"]),
            test_type=r["test_type"], date=started.date(), mission_day=r["mission_day"],
            started_at=started, finished_at=started + timedelta(seconds=r["duration_s"]),
            device=r["device"], trials=json.loads(r["raw"]), n_trials=r["n_trials"],
            mean_rt_ms=r["mean_rt_ms"], median_rt_ms=r["median_rt_ms"], speed=r["speed"],
            lapses=r["lapses"], false_starts=r["false_starts"], accuracy=r["accuracy"],
            valid=r["valid"], invalid_reason=r["invalid_reason"], source=r["source"], created_at=started,
        ))
    for r in data["weekly_assessments"]:
        taken = _ts(r["taken_at"])
        weekly_repo.add(WeeklyRecord(
            id=None, astronaut_id=r["astronaut_id"], client_request_id=UUID(r["client_request_id"]),
            date=taken.date(), mission_day=r["mission_day"], answers=json.loads(r["answers"]),
            who5_score=r["who5_score"], phq2_score=r["phq2_score"], gad2_score=r["gad2_score"],
            share_with_crew_medical=r["share_with_crew_medical"], source=r["source"], created_at=taken,
        ))
    return {name: len(data[name]) for name in SEED_FILES}


def load_seed_dir(folder: Path, checkin_repo: CheckinRepository, test_repo: CognitiveTestRepository,
                  weekly_repo: WeeklyRepository) -> dict[str, int]:
    missing = [f"{name}.json" for name in SEED_FILES if not (folder / f"{name}.json").is_file()]
    if missing:
        raise FileNotFoundError(
            f"Seed files not found in {folder}: {', '.join(missing)}. "
            "Generate them from the backend folder with: python -m scripts.seed_behavioral seed_output"
        )
    data = {name: json.loads((folder / f"{name}.json").read_text(encoding="utf-8")) for name in SEED_FILES}
    return load_seed_rows(data, checkin_repo, test_repo, weekly_repo)
