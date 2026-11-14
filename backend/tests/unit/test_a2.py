"""A2 kabul (DB'siz): kurallar, izinler, repository imzaları, JSON yardımcısı."""
import inspect
import re
from decimal import Decimal
from pathlib import Path

import pytest

from app.db.base import Base
from app.repositories.interfaces import (
    AlertRepository,
    IdentityRepository,
    JobRepository,
    ResultRepository,
)
from app.repositories.sqlalchemy_repository import SqlAlchemyRepository
from app.repositories.sqlalchemy_results import to_json

MIGRATION = Path(__file__).parents[2] / "migrations/versions/0003_sans_anomaly.py"


def checks(table: str) -> str:
    return " | ".join(
        str(c.sqltext) for c in Base.metadata.tables[table].constraints if hasattr(c, "sqltext")
    )


def test_a2_tables():
    expected = {
        "sans.oturum", "sans.test_kaydi", "sans.ortam", "sans.semptom", "sans.analiz",
        "sans.durum", "anomaly.MeasurementDefinitions", "anomaly.MeasurementRecords",
        "anomaly.anomaly_results",
    }
    assert expected <= set(Base.metadata.tables)


def test_retest_self_fk_and_rule():
    t = Base.metadata.tables["sans.oturum"]
    (fk,) = [fk for fk in t.foreign_keys if fk.parent.name == "retest_of"]
    assert fk.target_fullname == "sans.oturum.session_id"
    assert "retest_of<>session_id" in checks("sans.oturum")


def test_test_unit_pairs():
    c = checks("sans.test_kaydi")
    for pair in ("test='near_acuity' AND unit='logMAR'", "test='contrast' AND unit='logCS'",
                 "test='amsler' AND unit='cells'"):
        assert pair in c


@pytest.mark.parametrize("table", ["sans.oturum", "sans.test_kaydi", "sans.semptom",
                                   "sans.analiz", "anomaly.anomaly_results",
                                   "anomaly.MeasurementRecords"])
def test_negative_days_are_allowed(table):
    # Uçuş öncesi -60/-30/-10: gün alanlarında >=0 kuralı olmamalı
    assert not re.search(r"(flight_day|mission_day|\bday)\s*>=\s*0", checks(table))


def test_no_general_nonnegative_rule_on_values():
    # logMAR negatif olabilir
    assert "value>=0" not in checks("sans.test_kaydi").replace(" ", "")
    assert "value_num>=0" not in checks("anomaly.MeasurementRecords").replace(" ", "")


def test_app_role_permissions_in_0003():
    text = MIGRATION.read_text()
    perms = dict(re.findall(r'"(\w+\.\w+)": "([A-Z, ]+)"', text))
    assert perms["sans.durum"] == "SELECT, INSERT, UPDATE"
    assert perms["anomaly.anomaly_results"] == "SELECT, INSERT"  # sonuç değişmez
    assert all("DELETE" not in p for p in perms.values())


@pytest.mark.parametrize("proto", [IdentityRepository, ResultRepository, JobRepository, AlertRepository])
def test_sqlalchemy_repository_matches_protocols(proto):
    for name, fn in inspect.getmembers(proto, inspect.isfunction):
        if name.startswith("_"):
            continue
        impl = getattr(SqlAlchemyRepository, name)
        assert list(inspect.signature(impl).parameters) == list(inspect.signature(fn).parameters)


def test_to_json():
    assert to_json(None) is None
    assert to_json([{"m": "near_acuity", "v": Decimal("0.12")}]) == '[{"m":"near_acuity","v":0.12}]'
    assert to_json({"ş": "ğ"}) == '{"ş":"ğ"}'


def test_utc_naive():
    from datetime import UTC, datetime, timedelta, timezone

    from app.repositories.sqlalchemy_results import utc_naive

    ist = datetime(2027, 3, 20, 12, 30, tzinfo=timezone(timedelta(hours=3)))
    assert utc_naive(ist) == datetime(2027, 3, 20, 9, 30)
    assert utc_naive(datetime(2027, 3, 20, 9, 30, tzinfo=UTC)).tzinfo is None
