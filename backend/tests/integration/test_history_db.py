"""A5/Ö4 real SQL acceptance, enabled by RUN_DB_TESTS=1; all rows roll back."""

from contextlib import contextmanager
from decimal import Decimal
from uuid import uuid4

from app.core.snapshots import snapshot_hash
from app.models import MeasurementDefinition, MeasurementRecord
from app.repositories.sqlalchemy_repository import SqlAlchemyRepository
from app.schemas.history import HistoryPolicy, ThresholdPolicy
from app.services.history import HistoryPreparer
from tests.fixtures.history import NOW, job


def test_a5_read_freezes_original_values_and_policy(db, astronaut, tmp_path):
    code = "test_history_" + uuid4().hex
    db.add(MeasurementDefinition(measurement_code=code, module="physiological", canonical_unit="BPM",
                                 value_kind="numeric", protocol_version="test-v1",
                                 worsening_direction="context_dependent"))
    db.flush()
    source = MeasurementRecord(record_id=uuid4(), astronaut_id=astronaut, measurement_code=code,
                               client_request_id=uuid4(), eye_code="NA", value_num=Decimal("12.345678"),
                               valid=True, measured_date=NOW.date(), measured_at=None,
                               time_precision="date", mission_day=74, source="synthetic")
    db.add(source)
    db.flush()
    history_path, threshold_path = tmp_path / "history.json", tmp_path / "thresholds.json"
    policy = HistoryPolicy.model_validate({"version": "test-only", "features": [{
        "module": "physiological", "measurement": code, "unit": "BPM",
        "protocol_version": "test-v1", "definition_confirmed": True}]})
    history_path.write_text(policy.model_dump_json(), encoding="utf-8")
    threshold_path.write_text(ThresholdPolicy(version="test-unconfigured").model_dump_json(), encoding="utf-8")

    @contextmanager
    def sources():
        # Keep the existing rollback fixture's Session on this test thread. The
        # public async wrapper's thread ownership is covered separately offline.
        yield SqlAlchemyRepository(db)

    preparer = HistoryPreparer(sources, history_path, threshold_path, reference_date=NOW.date(), clock=lambda: NOW)
    snapshot = preparer._prepare(job().model_copy(update={"astronaut_id": astronaut}))
    frozen_hash = snapshot_hash(snapshot)
    assert snapshot["history_records"][0]["value_num_exact"] == "12.345678"
    assert snapshot["model_input"]["threshold_findings"][0]["status"] == "not_configured"
    # Fizyolojik kayıtlar değiştirilemez (astra_app'te UPDATE izni yok, şema kararı):
    # kaynakta "değişim" yeni ölçüm satırı olarak gelir. Dondurulmuş snapshot etkilenmemeli.
    db.add(MeasurementRecord(record_id=uuid4(), astronaut_id=astronaut, measurement_code=code,
                             client_request_id=uuid4(), eye_code="NA", value_num=Decimal("99"),
                             valid=True, measured_date=NOW.date(), measured_at=None,
                             time_precision="date", mission_day=74, source="synthetic"))
    db.flush()
    assert snapshot["history_records"][0]["value_num_exact"] == "12.345678"
    assert snapshot_hash(snapshot) == frozen_hash
