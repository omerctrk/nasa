"""AlertRepository'nin gerçek uygulaması (A3, sahip: Aybala).

- Alarm ve olay tekilliği filtreli UNIQUE indekslerle sağlanır; tekrar çağrı mevcut kaydı döner.
- Onay/kapatma koşullu UPDATE'tir: aynı anda iki operatör basarsa ilk onaylayan korunur.
- Alındı (receipt) teknik teslimdir, insan onayı değildir.
Commit yapılmaz (sözleşme §7).
"""
from __future__ import annotations

import json
import uuid

from sqlalchemy import exists, func, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.identity import User
from app.models.notifications import Alert, EventReceipt, NotificationEvent
from app.repositories.errors import InvalidStateTransition, NotFound, ValidationFailed
from app.repositories.records import (
    AlertCreate,
    AlertRecord,
    NotificationEventCreate,
    NotificationEventRecord,
)
from app.repositories.sqlalchemy_results import to_json
from app.schemas.common import (
    AlertStatus,
    AnalysisModule,
    Audience,
    EventType,
    Role,
    Severity,
)

NOW = text("SYSUTCDATETIME()")


def _alert(row: Alert) -> AlertRecord:
    return AlertRecord(
        alert_id=row.alert_id,
        astronaut_id=row.astronaut_id,
        module=AnalysisModule(row.module),
        severity=Severity(row.severity),
        status=AlertStatus(row.status),
        anomaly_result_id=row.anomaly_result_id,
        sans_analysis_id=row.sans_analysis_id,
        acknowledged_by=row.acknowledged_by,
        acknowledged_at=row.acknowledged_at,
        resolved_by=row.resolved_by,
        resolved_at=row.resolved_at,
        resolution_note=row.resolution_note,
        created_at=row.created_at,
    )


def _event(row: NotificationEvent) -> NotificationEventRecord:
    return NotificationEventRecord(
        event_id=row.event_id,
        event_type=EventType(row.event_type),
        audience=Audience(row.audience),
        target_user_id=row.target_user_id,
        job_id=row.job_id,
        alert_id=row.alert_id,
        payload=json.loads(row.payload_json),
        created_at=row.created_at,
        first_sent_at=row.first_sent_at,
        received_at=row.received_at,
        attempts=row.attempts,
    )


class SqlAlchemyAlertRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def _fresh(self, model, *where):
        return self.session.scalars(
            select(model).where(*where).execution_options(populate_existing=True)
        ).one_or_none()

    def create_alert(self, alert: AlertCreate) -> AlertRecord:
        source = (
            Alert.anomaly_result_id == alert.anomaly_result_id
            if alert.module is AnalysisModule.ANOMALY
            else Alert.sans_analysis_id == alert.sans_analysis_id
        )
        row = Alert(
            alert_id=uuid.uuid4(),
            astronaut_id=alert.astronaut_id,
            module=alert.module.value,
            severity=alert.severity.value,
            anomaly_result_id=alert.anomaly_result_id,
            sans_analysis_id=alert.sans_analysis_id,
        )
        try:
            with self.session.begin_nested():
                self.session.add(row)
        except IntegrityError:
            existing = self._fresh(Alert, source)
            if existing is None:
                raise
            return _alert(existing)  # sonuç başına tek alarm
        return _alert(self._fresh(Alert, Alert.alert_id == row.alert_id))

    def create_notification_event(self, event: NotificationEventCreate) -> NotificationEventRecord:
        subject = (
            NotificationEvent.job_id == event.job_id
            if event.job_id is not None
            else NotificationEvent.alert_id == event.alert_id
        )
        row = NotificationEvent(
            event_id=uuid.uuid4(),
            job_id=event.job_id,
            alert_id=event.alert_id,
            event_type=event.event_type.value,
            audience=event.audience.value,
            target_user_id=event.target_user_id,
            payload_json=to_json(event.payload),
        )
        try:
            with self.session.begin_nested():
                self.session.add(row)
        except IntegrityError:
            existing = self._fresh(
                NotificationEvent, subject, NotificationEvent.audience == event.audience.value
            )
            if existing is None:
                raise
            return _event(existing)
        return _event(self._fresh(NotificationEvent, NotificationEvent.event_id == row.event_id))

    def acknowledge_alert(self, alert_id: uuid.UUID, user_id: uuid.UUID) -> AlertRecord:
        # Yalnız OPEN iken yazılır → ilk onaylayan ve zamanı korunur.
        self.session.execute(
            update(Alert)
            .where(Alert.alert_id == alert_id, Alert.status == AlertStatus.OPEN.value)
            .values(status=AlertStatus.ACKNOWLEDGED.value, acknowledged_by=user_id,
                    acknowledged_at=NOW)
            .execution_options(synchronize_session=False)
        )
        row = self._fresh(Alert, Alert.alert_id == alert_id)
        if row is None:
            raise NotFound(str(alert_id))
        return _alert(row)

    def resolve_alert(self, alert_id: uuid.UUID, user_id: uuid.UUID, note: str) -> AlertRecord:
        note = note.strip()
        if not note or len(note) > 1000:
            raise ValidationFailed("Kapatma notu 1–1000 karakter olmalı")
        done = self.session.execute(
            update(Alert)
            .where(Alert.alert_id == alert_id, Alert.status == AlertStatus.ACKNOWLEDGED.value)
            .values(status=AlertStatus.RESOLVED.value, resolved_by=user_id, resolved_at=NOW,
                    resolution_note=note)
            .execution_options(synchronize_session=False)
        ).rowcount
        row = self._fresh(Alert, Alert.alert_id == alert_id)
        if row is None:
            raise NotFound(str(alert_id))
        if done != 1:
            raise InvalidStateTransition("Yalnız ACKNOWLEDGED alarm kapatılabilir")
        return _alert(row)

    def list_alerts(self, statuses: list[AlertStatus] | None = None,
                    astronaut_id: str | None = None) -> list[AlertRecord]:
        stmt = select(Alert).order_by(Alert.created_at.desc(), Alert.alert_id)
        if statuses:
            stmt = stmt.where(Alert.status.in_([AlertStatus(s).value for s in statuses]))
        if astronaut_id is not None:
            stmt = stmt.where(Alert.astronaut_id == astronaut_id)
        return [_alert(r) for r in self.session.scalars(stmt)]

    def record_receipt(self, event_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        try:
            with self.session.begin_nested():
                self.session.add(EventReceipt(event_id=event_id, user_id=user_id))
        except IntegrityError:
            already = self.session.scalar(
                select(func.count()).select_from(EventReceipt).where(
                    EventReceipt.event_id == event_id, EventReceipt.user_id == user_id
                )
            )
            if already:
                return False
            raise  # olay/kullanıcı yoksa FK hatası gizlenmez
        self.session.execute(
            update(NotificationEvent)
            .where(NotificationEvent.event_id == event_id, NotificationEvent.received_at.is_(None))
            .values(received_at=NOW)
            .execution_options(synchronize_session=False)
        )
        return True

    def list_pending_events(self, user_id: uuid.UUID) -> list[NotificationEventRecord]:
        role = self.session.scalar(select(User.role).where(User.user_id == user_id))
        if role is None:
            return []
        if role == Role.ASTRONAUT.value:
            target = NotificationEvent.target_user_id == user_id
        else:
            target = NotificationEvent.audience == Audience.GROUND_CONTROL.value
        received = exists().where(
            EventReceipt.event_id == NotificationEvent.event_id, EventReceipt.user_id == user_id
        )
        stmt = (
            select(NotificationEvent)
            .where(target, ~received)
            .order_by(NotificationEvent.created_at, NotificationEvent.event_id)
        )
        return [_event(r) for r in self.session.scalars(stmt)]

    def mark_event_sent(self, event_id: uuid.UUID) -> None:
        done = self.session.execute(
            update(NotificationEvent)
            .where(NotificationEvent.event_id == event_id)
            .values(first_sent_at=func.coalesce(NotificationEvent.first_sent_at, NOW),
                    attempts=NotificationEvent.attempts + 1)
            .execution_options(synchronize_session=False)
        ).rowcount
        if done != 1:
            raise NotFound(str(event_id))
