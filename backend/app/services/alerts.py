"""Analiz sonucu okuma ve kule alarm işlemleri (Ömer'in kalan kısmı, Aybala).

- Astronot yalnız kendi sonuç/alarmlarını OKUR; alarmı onaylama/kapatma yetkisi yalnız kuledir.
- Onay (ACKNOWLEDGED) ve kapatma (RESOLVED) koşullu UPDATE'tir: ilk onaylayan korunur.
- Kapatma yalnız ACKNOWLEDGED alarmda; aksi 409 INVALID_STATE_TRANSITION.
- Yazan uçlar burada commit eder (repository commit etmez, sözleşme §7).
"""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.analysis import AnomalyResult
from app.repositories.errors import NotFound
from app.repositories.records import AlertRecord
from app.repositories.sqlalchemy_repository import SqlAlchemyRepository
from app.schemas.common import AlertStatus
from app.schemas.notifications import AlertOut, AnomalyResultOut
from app.services.readings import _astronaut, check_range


def _aware(v: dt.datetime | None) -> dt.datetime | None:
    return v.replace(tzinfo=dt.UTC) if v is not None and v.tzinfo is None else v


def _alert_out(a: AlertRecord) -> AlertOut:
    return AlertOut(
        alert_id=a.alert_id, astronaut_id=a.astronaut_id, module=a.module, severity=a.severity,
        status=a.status, anomaly_result_id=a.anomaly_result_id,
        acknowledged_by=a.acknowledged_by, acknowledged_at=_aware(a.acknowledged_at),
        resolved_by=a.resolved_by, resolved_at=_aware(a.resolved_at),
        resolution_note=a.resolution_note, created_at=_aware(a.created_at))


def result(db: Session, result_id: uuid.UUID, astronaut_id: str | None = None) -> AnomalyResultOut:
    """astronaut_id verilirse yalnız o kişinin sonucu döner; başkasınınki 404 (varlık sızdırılmaz)."""
    r = SqlAlchemyRepository(db).get_anomaly_result(result_id)
    if r is None or (astronaut_id is not None and r.astronaut_id != astronaut_id):
        raise NotFound(str(result_id))
    return AnomalyResultOut(**r.model_dump(exclude={"measurement", "eye", "anomaly_score"}))


def results(db: Session, astronaut_id: str, start: dt.date, end: dt.date) -> list[AnomalyResultOut]:
    """[start, end) aralığında oluşturulan sonuçlar, eskiden yeniye."""
    check_range(start, end)
    _astronaut(db, astronaut_id)
    ids = db.scalars(
        select(AnomalyResult.id).where(
            AnomalyResult.astronaut_id == astronaut_id,
            AnomalyResult.created_at >= dt.datetime.combine(start, dt.time()),
            AnomalyResult.created_at < dt.datetime.combine(end, dt.time()))
        .order_by(AnomalyResult.created_at, AnomalyResult.id)
    ).all()
    return [result(db, i) for i in ids]


def alerts(db: Session, statuses: list[AlertStatus] | None = None,
           astronaut_id: str | None = None) -> list[AlertOut]:
    rows = SqlAlchemyRepository(db).list_alerts(statuses or None, astronaut_id)
    return [_alert_out(a) for a in rows]


def acknowledge(db: Session, alert_id: uuid.UUID, user_id: uuid.UUID) -> AlertOut:
    out = _alert_out(SqlAlchemyRepository(db).acknowledge_alert(alert_id, user_id))
    db.commit()
    return out


def resolve(db: Session, alert_id: uuid.UUID, user_id: uuid.UUID, note: str) -> AlertOut:
    out = _alert_out(SqlAlchemyRepository(db).resolve_alert(alert_id, user_id, note))
    db.commit()
    return out
