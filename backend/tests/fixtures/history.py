from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from app.repositories.records import AstronautRecord, JobRecord, JobRequestData
from app.schemas.common import MeasurementDTO
from app.schemas.history import HistoryPolicy, ThresholdPolicy
from app.services.thresholds import load_policy_json

ROOT = Path(__file__).parents[2]
NOW = datetime(2027, 3, 20, 12, tzinfo=UTC)
EYE_PROTOCOL_VERSION = "astra-v1"  # A6 MeasurementDefinitions seed


def profile(**changes):
    return AstronautRecord(**({"astronaut_id": "A007", "display_name": "Test", "mission_id": "M01",
                               "mission_start_date": date(2027, 1, 5), "mission_length_days": 180,
                               "is_display_only": False} | changes))


def job(scope="combined", **changes):
    return JobRecord(**({"job_id": UUID(int=10), "astronaut_id": "A007", "module": "anomaly",
                         "state": "SYNCING", "request": JobRequestData(module="anomaly", module_scope=scope),
                         "attempts": 1, "retry_cycle": 0, "has_snapshot": False,
                         "evaluation_status": None, "error_code": None, "anomaly_result_id": None,
                         "sans_analysis_id": None, "created_at": NOW, "updated_at": NOW} | changes))


def record(number=1, **changes):
    return MeasurementDTO(**({"record_id": f"physiological:{number}", "astronaut_id": "A007", "mission_id": "M01",
                              "module": "physiological", "measurement": "heart_rate", "value_num": Decimal("42"),
                              "value_text": None, "unit": "BPM", "protocol_version": "module-v2",
                              "measured_date": NOW.date(), "measured_at": None, "time_precision": "date",
                              "mission_day": 74, "eye": None, "source": "synthetic", "valid": True,
                              "quality_score": None, "session_id": None, "metadata_json": None} | changes))


def history_policy():
    return HistoryPolicy.model_validate(load_policy_json(ROOT / "config/history-policy.json"))


def thresholds():
    return ThresholdPolicy(version="test-unconfigured", rules=())
