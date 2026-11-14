"""ResultRepository'nin gerçek uygulaması (A2, sahip: Aybala).

save_anomaly_result / save_sans_analysis / update_sans_state.
Commit yapılmaz; Ömer'in "Transaction 2" bloğunda aynı Session ile çağrılır (sözleşme §7).
"""
from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.analysis import AnomalyResult
from app.models.sans import Analiz, Durum
from app.repositories.records import (
    AnomalyResultData,
    AnomalyResultRecord,
    SansAnalysisData,
    SansStateData,
)


def _default(o: Any) -> Any:
    if isinstance(o, Decimal):
        return float(o)
    if isinstance(o, uuid.UUID):
        return str(o)
    raise TypeError(f"JSON'a çevrilemiyor: {type(o).__name__}")


def utc_naive(value: datetime) -> datetime:
    """DATETIME2 saat dilimi tutmaz: saat dilimli değer UTC'ye çevrilip dilimi atılır."""
    if value.tzinfo is not None:
        value = value.astimezone(UTC).replace(tzinfo=None)
    return value


def to_json(value: Any) -> str | None:
    """NVARCHAR(MAX)+ISJSON alanları için. None → NULL."""
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=_default)


class SqlAlchemyResultRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def save_anomaly_result(self, result: AnomalyResultData) -> uuid.UUID:
        row = AnomalyResult(
            id=uuid.uuid4(),
            astronaut_id=result.astronaut_id,
            mission_day=result.mission_day,
            module_scope=result.module_scope.value,
            measurement=result.measurement,
            eye=result.eye.value if result.eye else None,
            algorithm=result.algorithm,
            model_version=result.model_version,
            anomaly_score=result.anomaly_score,
            is_anomaly=result.is_anomaly,
            level=result.level.value,
            summary=result.summary,
            drivers_json=to_json(result.drivers),
            baseline_status=result.baseline_status.value,
            data_quality_status=result.data_quality_status.value,
            recommendation=result.recommendation,
            data_cutoff_at=utc_naive(result.data_cutoff_at),
        )
        self.session.add(row)
        self.session.flush()
        return row.id

    def get_anomaly_result(self, result_id: uuid.UUID) -> AnomalyResultRecord | None:
        row = self.session.get(AnomalyResult, result_id)
        if row is None:
            return None
        return AnomalyResultRecord(
            id=row.id, created_at=row.created_at.replace(tzinfo=UTC),
            astronaut_id=row.astronaut_id, mission_day=row.mission_day,
            module_scope=row.module_scope, measurement=row.measurement, eye=row.eye,
            algorithm=row.algorithm, model_version=row.model_version,
            anomaly_score=row.anomaly_score, is_anomaly=row.is_anomaly, level=row.level,
            summary=row.summary, drivers=json.loads(row.drivers_json),
            baseline_status=row.baseline_status, data_quality_status=row.data_quality_status,
            recommendation=row.recommendation,
            data_cutoff_at=row.data_cutoff_at.replace(tzinfo=UTC),
        )

    def save_sans_analysis(self, result: SansAnalysisData) -> int:
        row = Analiz(
            astronaut_id=result.astronaut_id,
            session_id=result.session_id,
            flight_day=result.flight_day,
            created_at=func.sysutcdatetime(),  # DB saati (UTC)
            module="sans",
            risk=result.risk,
            level=result.level.value,
            state=result.state.value,
            summary=result.summary,
            recommendation=result.recommendation,
            drivers_json=to_json(result.drivers),
            trend_json=to_json(result.trend),
            model_version=result.model_version,
        )
        self.session.add(row)
        self.session.flush()  # IDENTITY değeri burada gelir
        return row.analysis_id

    def update_sans_state(
        self, new_state: SansStateData, expected_last_analysis_id: int | None
    ) -> bool:
        values = {
            "state": new_state.state.value,
            "since_flight_day": new_state.since_flight_day,
            "retest_due_day": new_state.retest_due_day,
            "last_analysis_id": new_state.last_analysis_id,
        }
        expected = (
            Durum.last_analysis_id.is_(None)
            if expected_last_analysis_id is None
            else Durum.last_analysis_id == expected_last_analysis_id
        )
        # Koşullu UPDATE: arada başka analiz durumu değiştirdiyse 0 satır etkilenir.
        changed = self.session.execute(
            update(Durum)
            .where(Durum.astronaut_id == new_state.astronaut_id, expected)
            .values(**values)
            .execution_options(synchronize_session=False)
        ).rowcount
        if changed == 1:
            return True
        if expected_last_analysis_id is not None:
            return False

        # İlk durum kaydı: PK çakışması = başka işlem önce yazdı → False.
        try:
            with self.session.begin_nested():
                self.session.add(Durum(astronaut_id=new_state.astronaut_id, **values))
        except IntegrityError:
            exists = self.session.scalar(
                select(func.count()).select_from(Durum).where(
                    Durum.astronaut_id == new_state.astronaut_id
                )
            )
            if exists:
                return False
            raise  # FK hatası vb. gerçek hata gizlenmez
        return True
