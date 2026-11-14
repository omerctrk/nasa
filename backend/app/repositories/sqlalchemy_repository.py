"""Servislerin kullandığı tek repository nesnesi (sözleşme §7):

    repo = SqlAlchemyRepository(session)

Her alanın gerçek uygulaması kendi dosyasındadır:
    A1  SqlAlchemyIdentityRepository   get_user_by_email, get_user_by_id, get_astronaut
    A2  SqlAlchemyResultRepository     save_anomaly_result, save_sans_analysis, update_sans_state
    A3  SqlAlchemyJobRepository        create_or_get_job … request_retry
    A3  SqlAlchemyAlertRepository      create_alert … mark_event_sent
    A5  SqlAlchemyMeasurementRepository get_measurements, get_sans_context (VIEW'lardan)
Artık sözleşmedeki Repository arayüzünün tamamı karşılanıyor.
"""
from sqlalchemy.orm import Session

from app.repositories.sqlalchemy_alerts import SqlAlchemyAlertRepository
from app.repositories.sqlalchemy_identity import SqlAlchemyIdentityRepository
from app.repositories.sqlalchemy_jobs import SqlAlchemyJobRepository
from app.repositories.sqlalchemy_measurements import SqlAlchemyMeasurementRepository
from app.repositories.sqlalchemy_results import SqlAlchemyResultRepository


class SqlAlchemyRepository(
    SqlAlchemyIdentityRepository,
    SqlAlchemyMeasurementRepository,
    SqlAlchemyResultRepository,
    SqlAlchemyJobRepository,
    SqlAlchemyAlertRepository,
):
    def __init__(self, session: Session) -> None:
        SqlAlchemyJobRepository.__init__(self, session)
