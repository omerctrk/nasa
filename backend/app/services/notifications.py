"""Authorization and transaction boundaries for notification HTTP reads/receipts."""

from uuid import UUID

from app.repositories.errors import NotFound
from app.repositories.records import NotificationEventRecord
from app.repositories.sqlalchemy_repository import SqlAlchemyRepository
from app.schemas.common import CurrentUser
from app.db.session import SessionLocal


def pending_events(user: CurrentUser) -> list[NotificationEventRecord]:
    with SessionLocal() as session, session.begin():
        return SqlAlchemyRepository(session).list_pending_events(user.user_id)


def receipt(event_id: UUID, user: CurrentUser) -> bool:
    with SessionLocal() as session, session.begin():
        repo = SqlAlchemyRepository(session)
        if not any(event.event_id == event_id for event in repo.list_pending_events(user.user_id)):
            raise NotFound(str(event_id))
        return repo.record_receipt(event_id, user.user_id)
