"""Bütün ORM modelleri burada import edilir; Alembic tek metadata'yı buradan görür.

Şema §11'e göre eklenecek dosyalar (sahip: Aybala):
    identity.py       Missions, Astronauts, Users                      (A1)
    sans.py           oturum, test_kaydi, ortam, semptom, analiz, durum (A2)
    measurements.py   MeasurementDefinitions, MeasurementRecords       (A2)
    analysis.py       anomaly_results, AnalysisJobs                    (A2 + A3)
    notifications.py  Alerts, NotificationEvents, EventReceipts        (A3)
    behavioral.py     checkins, weekly_assessments, cognitive_tests    (A4)
    evaluation.py     gercek_durum                                     (A4)

VIEW'lar (sans.gorev, sans.profil, anomaly.v_measurements) yazılabilir tablo gibi
modellenmez; migration içinde CREATE VIEW ile oluşturulur (A5).
Yeni bir model dosyası buraya import edilmezse tablo migration'a girmez.
"""
from app.models.identity import Astronaut, Mission, User  # noqa: E402  (A1)
from app.models.sans import Analiz, Durum, Ortam, Oturum, Semptom, TestKaydi  # noqa: E402  (A2)
from app.models.measurements import MeasurementDefinition, MeasurementRecord  # noqa: E402  (A2)
from app.models.analysis import AnomalyResult  # noqa: E402  (A2)

__all__ = [
    "Analiz", "AnomalyResult", "Astronaut", "Durum", "MeasurementDefinition",
    "MeasurementRecord", "Mission", "Ortam", "Oturum", "Semptom", "TestKaydi", "User",
]
