from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.errors import ApiError
from app.schemas.common import CurrentUser, Role
from app.services import results


def test_anomaly_result_is_scoped_to_owner_or_ground(monkeypatch):
    result_id = uuid4()
    row = SimpleNamespace(
        id=result_id, astronaut_id="A007", mission_day=74,
        created_at=datetime(2026, 11, 15), module_scope="combined", measurement=None,
        eye=None, algorithm="test", model_version="test", anomaly_score=None,
        is_anomaly=False, level="normal", summary="test", drivers_json="[]",
        baseline_status="ready", data_quality_status="valid", recommendation="test",
        data_cutoff_at=datetime(2026, 11, 15),
    )

    class Session:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def get(self, model, identity):
            assert identity == result_id
            return row

    monkeypatch.setattr(results, "SessionLocal", Session)
    other = CurrentUser(user_id=uuid4(), role=Role.ASTRONAUT, astronaut_id="A008")
    with pytest.raises(ApiError) as hidden:
        results.get_anomaly_result(result_id, other)
    assert hidden.value.status_code == 404
    owner = other.model_copy(update={"astronaut_id": "A007"})
    assert results.get_anomaly_result(result_id, owner).created_at.isoformat().endswith("+00:00")
    ground = CurrentUser(user_id=uuid4(), role=Role.GROUND_CONTROL, astronaut_id=None)
    assert results.get_anomaly_result(result_id, ground).id == result_id
