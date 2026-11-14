"""Connect Ö4 preparation to the A5 measurement repository; no fake fallback."""

from contextlib import contextmanager

from app.repositories.sqlalchemy_repository import SqlAlchemyRepository
from app.services.history import HistoryPreparer


@contextmanager
def history_sources():
    from app.db.session import SessionLocal
    with SessionLocal.begin() as session:
        yield SqlAlchemyRepository(session)


def configure_history(app, settings):
    if not callable(getattr(SqlAlchemyRepository, "get_measurements", None)):
        app.state.history_preparer = None
        return
    app.state.history_preparer = HistoryPreparer(
        history_sources, settings.history_policy_path, settings.threshold_policy_path,
        reference_date=settings.anomaly_reference_date,
    )
