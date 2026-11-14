"""Repository sözleşmesi (ortak, §6): fonksiyon adları, parametreler ve dönüş tipleri.

- Gerçek uygulama: Aybala, app/repositories/sqlalchemy_*.py  → SqlAlchemyRepository(session)
- Fake uygulama:   Ömer,   tests/fakes/
İkisi de bu Protocol'leri karşılar; servis kodu yalnız buradaki tiplere bağımlıdır.

Ortak kurallar:
- Senkron. Repository commit/rollback YAPMAZ; transaction servis sınırındadır (§7).
- Tarih aralıkları başlangıç DAHİL, bitiş HARİÇ [start, end).
- Listeler (tarih/zaman, record_id) ile kararlı sıralanır.
- ORM nesnesi dönmez; app/repositories/records.py modelleri döner.
- Tekillik DB UNIQUE kuralıyla sağlanır; "önce bak sonra ekle" tek başına yeterli değildir.
- Hatalar app/repositories/errors.py içindedir.

"EK" işaretli fonksiyonlar ek açıklamadaki tabloda yoktu; ilgili endpoint/akış için
gerekli olduğundan eklendi (contracts/backend-contract.md §6.1).
"""
from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Protocol, runtime_checkable

from app.repositories.records import (
    AlertCreate,
    AlertRecord,
    AnomalyResultData,
    AstronautRecord,
    ClaimedJob,
    CreateJobResult,
    JobOutcome,
    JobRecord,
    JobRequestData,
    JobScope,
    NotificationEventCreate,
    NotificationEventRecord,
    RecoveredJob,
    SansAnalysisData,
    SansContext,
    SansStateData,
    UserRecord,
)
from app.schemas.common import AlertStatus, AnalysisModule, MeasurementDTO


@runtime_checkable
class IdentityRepository(Protocol):
    def get_user_by_email(self, email: str) -> UserRecord | None:
        """E-posta normalize edilerek (trim + küçük harf) aranır."""

    def get_user_by_id(self, user_id: uuid.UUID) -> UserRecord | None: ...

    def get_astronaut(self, astronaut_id: str) -> AstronautRecord | None: ...


@runtime_checkable
class MeasurementRepository(Protocol):
    def get_measurements(
        self, astronaut_id: str, start_date: date, end_date: date
    ) -> list[MeasurementDTO]:
        """[start_date, end_date) aralığındaki tüm modüllerin ortak ölçümleri
        (anomaly.v_measurements). measured_date, record_id ile sıralı."""

    def get_sans_context(
        self, astronaut_id: str, session_id: str, data_cutoff_at: datetime
    ) -> SansContext | None:
        """Profil, uçuş öncesi oturumlar, göz geçmişi, CO₂, semptom ve güncel durum.
        Oturum yoksa veya astronota ait değilse None."""


@runtime_checkable
class JobApiRepository(Protocol):
    """Ö2 subset; API fakes do not need to implement worker operations."""
    def create_or_get_job(
        self,
        scope: JobScope,
        idempotency_key: uuid.UUID,
        request_hash: str,
        request: JobRequestData,
    ) -> CreateJobResult:
        """Aynı anahtar + aynı hash → mevcut iş (created=False).
        Aynı anahtar + farklı hash → IdempotencyConflict."""

    def get_job(self, job_id: uuid.UUID, scope: JobScope) -> JobRecord | None:
        """Kapsam dışındaki iş için de None (404, varlığı sızdırılmaz)."""

    def request_retry(self, job_id: uuid.UUID, scope: JobScope) -> JobRecord:
        """Yalnız FAILED iş: retry_cycle+1, attempts=0, QUEUED. Snapshot korunur.
        Geçiş atomiktir. Başka durumda InvalidStateTransition, kapsam dışıysa NotFound."""


@runtime_checkable
class JobRepository(JobApiRepository, Protocol):
    def claim_next_job(self, lease_seconds: int,
                       modules: tuple[AnalysisModule, ...] = tuple(AnalysisModule)) -> ClaimedJob | None:
        """Yalnız etkin modüllerdeki en eski QUEUED işi atomik sahiplenir: SYNCING, yeni lease,
        attempts+1. Aynı astronotun SANS işlerini atomik olarak sıralar."""

    def renew_job_lease(
        self, job_id: uuid.UUID, lease_token: uuid.UUID, lease_seconds: int
    ) -> bool:
        """Token + aktif durum + lease_until>DB now koşuluyla yeniler.
        Süresi geçmiş lease yeniden canlandırılmaz; geçerli değilse False."""

    def recover_expired_jobs(self, max_attempts: int = 2) -> list[RecoveredJob]:
        """lease_until < DB'nin SYSUTCDATETIME()'ı olan işleri kurtarır:
        Anomali tekrar hakkı varsa QUEUED, yoksa FAILED. ANALYZING SANS işi
        SANS_RECONCILIATION_REQUIRED ile FAILED olur; kör POST tekrarı yapılmaz."""

    def reschedule_job(
        self, job_id: uuid.UUID, lease_token: uuid.UUID, delay_seconds: float,
        error_code: str, max_attempts: int = 2,
    ) -> JobRecord:
        """Ö3: geçerli lease + anomaly + attempts<max_attempts koşuluyla QUEUED.
        next_attempt_at DB saati+delay, lease temizlenir; snapshot/hash korunur.
        Sahiplik/süre yoksa LeaseLost; uygun değilse InvalidStateTransition."""

    def save_input_snapshot(
        self,
        job_id: uuid.UUID,
        lease_token: uuid.UUID,
        snapshot: dict[str, Any],
        input_hash: str,
    ) -> None:
        """İlk kayıt yazılır ve iş ANALYZING olur. Aynı hash → içerik değişmez,
        ama retry SYNCING→ANALYZING geçişi yine yapılır.
        Farklı hash → SnapshotConflict. Sahiplik yoksa → LeaseLost."""

    def finalize_job(
        self, job_id: uuid.UUID, lease_token: uuid.UUID, outcome: JobOutcome
    ) -> JobRecord:
        """Token + aktif durum + lease_until>DB now kontrollü tamamlanma;
        lease temizlenir. Geçerli sahiplik yoksa LeaseLost, sonuç yazımı rollback edilir."""

@runtime_checkable
class ResultRepository(Protocol):
    def save_anomaly_result(self, result: AnomalyResultData) -> uuid.UUID: ...

    def save_sans_analysis(self, result: SansAnalysisData) -> int: ...

    def update_sans_state(
        self, new_state: SansStateData, expected_last_analysis_id: int | None
    ) -> bool:
        """Güncel durumun last_analysis_id'si beklenenle aynıysa günceller (yoksa oluşturur);
        arada başka analiz durumu değiştirdiyse False (iyimser eşzamanlılık)."""


@runtime_checkable
class AlertRepository(Protocol):
    def create_alert(self, alert: AlertCreate) -> AlertRecord:
        """Bir model sonucu için tek alarm: aynı sonuç için tekrar çağrıda mevcut alarm döner."""

    def create_notification_event(self, event: NotificationEventCreate) -> NotificationEventRecord:
        """(job_id, audience) / (alert_id, audience) başına tek olay; tekrar çağrıda mevcut döner."""

    def acknowledge_alert(self, alert_id: uuid.UUID, user_id: uuid.UUID) -> AlertRecord:
        """OPEN → ACKNOWLEDGED. Zaten onaylıysa ilk onaylayan/zaman korunur ve mevcut kayıt
        döner. Alarm yoksa NotFound."""

    def resolve_alert(self, alert_id: uuid.UUID, user_id: uuid.UUID, note: str) -> AlertRecord:
        """ACKNOWLEDGED → RESOLVED (not boş olamaz). OPEN veya zaten RESOLVED ise
        InvalidStateTransition; yoksa NotFound."""

    def list_alerts(
        self, statuses: list[AlertStatus] | None = None, astronaut_id: str | None = None
    ) -> list[AlertRecord]:
        """EK — kule paneli ve yeniden bağlanmada aktif alarm listesi; created_at DESC."""

    def record_receipt(self, event_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """Teknik teslim alındısı (insan onayı değil). İlk kayıtta True, tekrarında False.
        Yetki kontrolü servis tarafındadır."""

    def list_pending_events(self, user_id: uuid.UUID) -> list[NotificationEventRecord]:
        """EK — kullanıcının alındısı olmayan olayları (yeniden bağlanma/outbox); created_at ASC."""

    def mark_event_sent(self, event_id: uuid.UUID) -> None:
        """EK — first_sent_at ilk kez set edilir, attempts+1. Teslim kanıtı değildir."""


class Repository(
    IdentityRepository,
    MeasurementRepository,
    JobRepository,
    ResultRepository,
    AlertRepository,
    Protocol,
):
    """Servislerin aldığı tek nesne: repo = SqlAlchemyRepository(session)."""
