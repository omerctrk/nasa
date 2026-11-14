"""Authorization and transaction boundaries for alerts and event receipts."""

from uuid import UUID

from app.repositories.errors import NotFound
from app.repositories.records import AlertRecord, NotificationEventRecord
from app.repositories.sqlalchemy_repository import SqlAlchemyRepository
from app.schemas.common import AlertStatus, CurrentUser
from app.db.session import SessionLocal


def list_alerts(status: AlertStatus | None = None) -> list[AlertRecord]:
    with SessionLocal() as session, session.begin():
        return SqlAlchemyRepository(session).list_alerts([status] if status else None)


def acknowledge_alert(alert_id: UUID, user: CurrentUser) -> AlertRecord:
    with SessionLocal() as session, session.begin():
        return SqlAlchemyRepository(session).acknowledge_alert(alert_id, user.user_id)


def resolve_alert(alert_id: UUID, user: CurrentUser, note: str) -> AlertRecord:
    with SessionLocal() as session, session.begin():
        return SqlAlchemyRepository(session).resolve_alert(alert_id, user.user_id, note)


def pending_events(user: CurrentUser) -> list[NotificationEventRecord]:
    with SessionLocal() as session, session.begin():
        return SqlAlchemyRepository(session).list_pending_events(user.user_id)


def pending_for_delivery(user: CurrentUser, sent_in_connection: set[UUID]) -> list[NotificationEventRecord]:
    """Record each delivery attempt before emitting; reconnects replay unreceipted events."""
    with SessionLocal() as session, session.begin():
        repo = SqlAlchemyRepository(session)
        events = [event for event in repo.list_pending_events(user.user_id)
                  if event.event_id not in sent_in_connection]
        for event in events:
            repo.mark_event_sent(event.event_id)
        return events


def receipt(event_id: UUID, user: CurrentUser) -> bool:
    with SessionLocal() as session, session.begin():
        repo = SqlAlchemyRepository(session)
        if not any(event.event_id == event_id for event in repo.list_pending_events(user.user_id)):
            raise NotFound(str(event_id))
        return repo.record_receipt(event_id, user.user_id)
