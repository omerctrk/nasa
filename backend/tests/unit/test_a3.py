"""A3 kabul (DB'siz): iş sonucu kuralları, hash doğrulama, ops izinleri."""
import re
import uuid
from pathlib import Path

import pytest

from app.db.base import Base
from app.repositories.errors import ValidationFailed
from app.repositories.records import JobOutcome
from app.repositories.sqlalchemy_jobs import SqlAlchemyJobRepository, _hex64

MIGRATION = Path(__file__).parents[2] / "migrations/versions/0004_ops.py"
check = SqlAlchemyJobRepository._check_outcome
RID = uuid.uuid4()


def test_ops_tables_and_request_json():
    assert {"ops.AnalysisJobs", "ops.Alerts", "ops.NotificationEvents",
            "ops.EventReceipts"} <= set(Base.metadata.tables)
    col = Base.metadata.tables["ops.AnalysisJobs"].c.request_json
    assert col.nullable is False


@pytest.mark.parametrize(("module", "outcome"), [
    ("anomaly", JobOutcome(state="COMPLETED", evaluation_status="evaluated", anomaly_result_id=RID)),
    ("sans", JobOutcome(state="COMPLETED", evaluation_status="evaluated", sans_analysis_id=7)),
    ("anomaly", JobOutcome(state="COMPLETED", evaluation_status="insufficient_data",
                           outcome={"reason": "az veri"})),
    ("sans", JobOutcome(state="FAILED", error_code="SANS_TIMEOUT")),
])
def test_valid_outcomes(module, outcome):
    check(module, outcome)


@pytest.mark.parametrize(("module", "outcome"), [
    ("anomaly", JobOutcome(state="COMPLETED", evaluation_status="evaluated", sans_analysis_id=7)),
    ("sans", JobOutcome(state="COMPLETED", evaluation_status="evaluated")),
    ("anomaly", JobOutcome(state="COMPLETED", evaluation_status="insufficient_data")),
    ("anomaly", JobOutcome(state="COMPLETED", evaluation_status="invalid_data",
                           anomaly_result_id=RID, outcome={})),
    ("anomaly", JobOutcome(state="COMPLETED")),
    ("anomaly", JobOutcome(state="FAILED", anomaly_result_id=RID)),
])
def test_invalid_outcomes(module, outcome):
    with pytest.raises(ValidationFailed):
        check(module, outcome)


def test_hash_format():
    assert _hex64("a" * 64, "h")
    for bad in ("A" * 64, "a" * 63, "g" * 64):
        with pytest.raises(ValidationFailed):
            _hex64(bad, "h")


def test_ops_permissions():
    perms = dict(re.findall(r'"(\w+\.\w+)": "([A-Z, ]+)"', MIGRATION.read_text()))
    assert perms["ops.EventReceipts"] == "SELECT, INSERT"  # alındı değişmez
    assert all("DELETE" not in p for p in perms.values())
