"""Demo takvim hizalaması: son senaryo günü (74) = bugün; görev günü korunur. DB gerektirmez.

Gerçek SQL Server'da DATEADD/DATEDIFF ile kaydırma tests/e2e (migrate/sa) içinde doğrulanır.
"""
import datetime as dt
import types

import pytest
from sqlalchemy.dialects import mssql

from app.models.behavioral import Checkin
from app.models.measurements import MeasurementRecord
from scripts import demo_data
from scripts import realign_demo as ra

TODAY = dt.date(2026, 11, 15)


def test_shift_puts_last_scenario_day_on_today():
    start = dt.date(2026, 9, 1)  # eski hizalama: 74. gün = dün
    delta = ra.shift_days(start, TODAY)
    assert delta == 1
    assert (start + dt.timedelta(days=delta)) + dt.timedelta(days=ra.LAST_DAY) == TODAY
    assert ra.shift_days(dt.date(2026, 9, 2), TODAY) == 0           # zaten hizalı
    assert ra.shift_days(dt.date(2027, 1, 5), TODAY) < 0            # şema tarihi (gelecek) → geri
    assert ra.LAST_DAY == demo_data.LAST_DAY


def test_each_table_shifts_in_one_dateadd_update():
    stmt = ra.shift_statement(MeasurementRecord, MeasurementRecord.astronaut_id,
                              (MeasurementRecord.measured_date, MeasurementRecord.measured_at),
                              ["A007"], 1)
    sql = str(stmt.compile(dialect=mssql.dialect(), compile_kwargs={"literal_binds": True}))
    assert sql.count("UPDATE") == 1
    assert "measured_date=dateadd(day, 1, anomaly.[MeasurementRecords].measured_date)" in sql
    assert "measured_at=dateadd(day, 1, anomaly.[MeasurementRecords].measured_at)" in sql
    assert "mission_day" not in sql  # görev günü değişmez
    assert "astronaut_id IN (N'A007')" in sql


class FakeDB:
    """realign()'ın sorduğu sayımları SQL metnine göre yanıtlar; yazılanları kaydeder."""

    def __init__(self, start, late=0, broken=0):
        self.mission = types.SimpleNamespace(start_date=start)
        self.late, self.broken, self.executed, self.flushed = late, broken, [], False

    def get(self, _model, _key):
        return self.mission

    def scalars(self, _stmt):
        return iter(["A007", "A008"])

    def scalar(self, stmt):
        sql = str(stmt.compile(dialect=mssql.dialect()))
        if "datediff" in sql.lower():
            return self.broken
        if "mission_day >" in sql:
            return self.late
        return 10

    def execute(self, stmt):
        self.executed.append(str(stmt.compile(dialect=mssql.dialect())))

    def flush(self):
        self.flushed = True


def test_realign_moves_start_and_every_dated_table():
    db = FakeDB(dt.date(2026, 9, 1))
    report = ra.realign(db, TODAY, apply=True)
    assert report["shift_days"] == 1 and report["start_after"] == "2026-09-02"
    assert db.mission.start_date == dt.date(2026, 9, 2) and db.flushed
    tables = " ".join(db.executed)
    for name in ("checkins", "cognitive_tests", "weekly_assessments", "MeasurementRecords"):
        assert name in tables
    assert len(db.executed) == 4


def test_already_aligned_changes_nothing():
    db = FakeDB(dt.date(2026, 9, 2))
    report = ra.realign(db, TODAY, apply=True)
    assert report["mode"] == "already_aligned" and db.executed == []


def test_refuses_when_records_exist_after_scenario_end():
    db = FakeDB(dt.date(2026, 9, 1), late=3)
    with pytest.raises(ra.RealignRefused, match="74"):
        ra.realign(db, TODAY, apply=True)
    assert db.executed == [] and db.mission.start_date == dt.date(2026, 9, 1)


def test_refuses_when_dates_disagree_with_mission_day():
    db = FakeDB(dt.date(2026, 9, 1), broken=2)
    with pytest.raises(ra.RealignRefused, match="tutmayan"):
        ra.realign(db, TODAY, apply=True)
    assert db.executed == []


def test_demo_data_aligns_last_day_to_today(monkeypatch):
    class Clock(dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return dt.datetime(2026, 11, 15, 9, tzinfo=dt.UTC)
    monkeypatch.setattr(demo_data.dt, "datetime", Clock)
    mission = types.SimpleNamespace(start_date=dt.date(2027, 1, 5))

    class DB:
        def scalar(self, _):
            return None  # henüz seed check-in'i yok

        def flush(self):
            pass
    demo_data._align_to_today(DB(), mission)
    assert mission.start_date + dt.timedelta(days=demo_data.LAST_DAY) == TODAY


def test_checkin_model_used_for_day_consistency():
    assert ra.TABLES[0][1] is Checkin and ra.TABLES[0][4] is Checkin.date
