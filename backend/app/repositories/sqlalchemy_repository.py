"""Servislerin kullandığı tek repository nesnesi (sözleşme §7):

    repo = SqlAlchemyRepository(session)

Her alanın gerçek uygulaması kendi dosyasındadır ve tablolar oluştukça buraya eklenir:
    A1  SqlAlchemyIdentityRepository   get_user_by_email, get_user_by_id, get_astronaut
    A2  SqlAlchemyResultRepository     save_anomaly_result, save_sans_analysis, update_sans_state
    A3  iş, alarm, bildirim             (sonraki)
    A5  get_measurements, get_sans_context (VIEW'lardan; sonraki)
O zamana kadar Ömer eksik kısımlar için tests/fakes/ uygulamasıyla çalışır.
"""
from sqlalchemy.orm import Session

from app.repositories.sqlalchemy_identity import SqlAlchemyIdentityRepository
from app.repositories.sqlalchemy_results import SqlAlchemyResultRepository


class SqlAlchemyRepository(SqlAlchemyIdentityRepository, SqlAlchemyResultRepository):
    def __init__(self, session: Session) -> None:
        self.session = session
