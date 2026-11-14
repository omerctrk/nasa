"""Read anomaly results with the same astronaut/ground scope as analysis jobs."""

import json
from uuid import UUID

from app.core.errors import ApiError
from app.db.session import SessionLocal
from app.models.analysis import AnomalyResult
from app.schemas.common import CurrentUser, ErrorCode, Role
from app.schemas.results import AnomalyResultOut


def get_anomaly_result(result_id: UUID, user: CurrentUser) -> AnomalyResultOut:
    with SessionLocal() as session:
        row = session.get(AnomalyResult, result_id)
        if row is None or (user.role is Role.ASTRONAUT and row.astronaut_id != user.astronaut_id):
            raise ApiError(404, ErrorCode.NOT_FOUND)
        return AnomalyResultOut(
            id=row.id, astronaut_id=row.astronaut_id, mission_day=row.mission_day,
            created_at=row.created_at, module_scope=row.module_scope,
            measurement=row.measurement, eye=row.eye, algorithm=row.algorithm,
            model_version=row.model_version, anomaly_score=row.anomaly_score,
            is_anomaly=row.is_anomaly, level=row.level, summary=row.summary,
            drivers_json=json.loads(row.drivers_json), baseline_status=row.baseline_status,
            data_quality_status=row.data_quality_status, recommendation=row.recommendation,
            data_cutoff_at=row.data_cutoff_at,
        )
