"""A4 gerçek DB kabulü: eval izolasyonu, check-in tekilliği, bilişsel metrik kuralı."""
import uuid
from datetime import date, datetime, time

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.models import Checkin, CognitiveTest


def test_app_cannot_read_evaluation(db):
    with pytest.raises(DBAPIError, match="SELECT permission"), db.begin_nested():
        db.execute(text("SELECT TOP 1 * FROM evaluation.gercek_durum"))


def checkin(astronaut, **kw):
    now = datetime(2027, 3, 20, 9, 0)
    base = dict(date=date(2027, 3, 20), mission_day=74, mood=6, energy=5, stress=4, loneliness=1,
                crew=3, mood_index=60.0, bed_time=time(23, 0), wake_time=time(7, 0),
                sleep_hours=8.0, sleep_quality=4, source="manual", created_at=now,
                updated_at=now, astronaut_id=astronaut)
    return Checkin(**(base | kw))


def test_one_checkin_per_person_and_day(db, astronaut):
    db.add(checkin(astronaut))
    db.flush()
    with pytest.raises(IntegrityError), db.begin_nested():
        db.add(checkin(astronaut))


def test_pvt_cannot_have_accuracy(db, astronaut):
    with pytest.raises(IntegrityError), db.begin_nested():
        db.add(CognitiveTest(
            taken_at=datetime(2027, 3, 20, 10), mission_day=74, test_type="pvt", duration_s=180,
            n_trials=50, mean_rt_ms=300.0, accuracy=0.9, valid=True, device="tablet",
            raw="[]", source="manual", astronaut_id=astronaut, client_request_id=uuid.uuid4()))
