"""Repository'lerin aldığı ve döndürdüğü adlandırılmış veri modelleri (ortak sözleşme §6).

Repository dışarıya canlı ORM nesnesi vermez; bu modeller verilir. Böylece Ömer'in
tests/fakes/ uygulaması ile Aybala'nın SQLAlchemy uygulaması birbirinin yerine geçer.
Hepsi değiştirilemez (frozen) ve bilinmeyen alanı reddeder.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.common import (
    AlertStatus,
    AnalysisModule,
    AnomalyLevel,
    Audience,
    BaselineStatus,
    DataQualityStatus,
    EvaluationStatus,
    EventType,
    Eye,
    JobState,
    MeasurementDTO,
    ModuleScope,
    Role,
    SansLevel,
    SansState,
    Severity,
)


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


# --- Kimlik ------------------------------------------------------------------------


class UserRecord(Record):
    user_id: uuid.UUID
    email: str
    password_hash: str  # yalnız auth servisi kullanır; API yanıtına konmaz
    role: Role
    is_active: bool
    astronaut_id: str | None
    created_at: datetime


class AstronautRecord(Record):
    astronaut_id: str
    display_name: str
    mission_id: str
    mission_start_date: date  # görev günü 0
    mission_length_days: int
    is_display_only: bool
    # SANS profil alanları (genel anomali girdisine otomatik eklenmez)
    age: int | None = None
    sex: str | None = None
    weight_kg: Decimal | None = None
    prior_flight: bool | None = None
    prior_sans: bool | None = None
    mtrr66_g: int | None = None
    shmt1_1420_c: int | None = None
    b_vit_status: Decimal | None = None
    optic_cup_vol: Decimal | None = None


# --- SANS bağlamı ------------------------------------------------------------------


class SansSessionRecord(Record):
    session_id: str
    flight_day: int
    date: date
    is_retest: bool
    retest_of: str | None
    quality_score: Decimal
    source: str  # kaynak değer: synthetic / test_screen / manual


class Co2Day(Record):
    day: int
    co2_mmhg: Decimal
    source: str  # synthetic / osdr


class SymptomDay(Record):
    flight_day: int
    headache: bool


class SansStateRecord(Record):
    astronaut_id: str
    state: SansState
    since_flight_day: int
    retest_due_day: int | None
    last_analysis_id: int | None


class SansContext(Record):
    """get_sans_context çıktısı: analiz edilen oturumun flight_day'inden sonraki hiçbir kayıt
    içermez (görev takvimi simüle olduğu için kesim görev gününe göredir)."""

    profile: AstronautRecord
    session: SansSessionRecord  # analiz edilen oturum
    baseline_sessions: list[SansSessionRecord]  # uçuş öncesi (flight_day < 0)
    eye_history: list[MeasurementDTO]  # module=sans, eye dolu
    co2: list[Co2Day]
    symptoms: list[SymptomDay]
    state: SansStateRecord | None
    data_cutoff_at: datetime


# --- İşler -------------------------------------------------------------------------


class JobRequestData(Record):
    """Doğrulanmış ve normalize edilmiş iş isteği (hash bunun üzerinden hesaplanır)."""

    module: AnalysisModule
    module_scope: ModuleScope | None = None  # yalnız anomaly
    session_id: str | None = None  # yalnız sans

    @model_validator(mode="after")
    def _by_module(self) -> JobRequestData:
        if self.module is AnalysisModule.ANOMALY and (self.module_scope is None or self.session_id):
            raise ValueError("anomaly işi module_scope ister, session_id almaz")
        if self.module is AnalysisModule.SANS and (self.session_id is None or self.module_scope):
            raise ValueError("sans işi session_id ister, module_scope almaz")
        return self


class JobScope(Record):
    """İşi oluşturan/okuyan kullanıcının kapsamı. Astronot yalnız kendi işini görür."""

    user_id: uuid.UUID
    role: Role
    astronaut_id: str | None


class JobRecord(Record):
    job_id: uuid.UUID
    astronaut_id: str
    module: AnalysisModule
    state: JobState
    request: JobRequestData
    attempts: int
    retry_cycle: int
    has_snapshot: bool
    evaluation_status: EvaluationStatus | None
    error_code: str | None
    anomaly_result_id: uuid.UUID | None
    sans_analysis_id: int | None
    created_at: datetime
    updated_at: datetime


class CreateJobResult(Record):
    job: JobRecord
    created: bool  # False: aynı anahtar + aynı hash ile mevcut iş döndü


class ClaimedJob(Record):
    job: JobRecord
    lease_token: uuid.UUID
    lease_until: datetime
    input_snapshot: dict[str, Any] | None  # retry'da korunmuş snapshot varsa dolu
    input_hash: str | None


class RecoveredJob(Record):
    job_id: uuid.UUID
    previous_state: JobState
    new_state: JobState  # QUEUED (tekrar hakkı var) veya FAILED


class JobOutcome(Record):
    """finalize_job girdisi."""

    state: JobState  # COMPLETED veya FAILED
    evaluation_status: EvaluationStatus | None = None
    anomaly_result_id: uuid.UUID | None = None
    sans_analysis_id: int | None = None
    outcome: dict[str, Any] | None = None  # değerlendirme yapılamadıysa açıklama
    error_code: str | None = Field(default=None, max_length=40)
    provider_metadata: dict[str, Any] | None = None

    @model_validator(mode="after")
    def _final_state(self) -> JobOutcome:
        if self.state not in (JobState.COMPLETED, JobState.FAILED):
            raise ValueError("finalize_job yalnız COMPLETED veya FAILED yazar")
        return self


# --- Sonuçlar ----------------------------------------------------------------------


class AnomalyResultData(Record):
    astronaut_id: str
    mission_day: int | None
    module_scope: ModuleScope
    measurement: str | None = None
    eye: Eye | None = None
    algorithm: str = "threshold_rules_plus_llm"
    model_version: str | None
    anomaly_score: float | None = None  # bu demoda NULL
    is_anomaly: bool
    level: AnomalyLevel
    summary: str = Field(max_length=4000)
    drivers: list[Any]
    baseline_status: BaselineStatus
    data_quality_status: DataQualityStatus
    recommendation: str = Field(max_length=2000)
    data_cutoff_at: datetime


class SansAnalysisData(Record):
    astronaut_id: str
    session_id: str | None
    flight_day: int
    risk: Decimal = Field(ge=0, le=1)
    level: SansLevel
    state: SansState
    summary: str | None = Field(default=None, max_length=4000)
    recommendation: str | None = Field(default=None, max_length=2000)
    drivers: list[Any] | None = None
    trend: Any | None = None
    model_version: str | None = None


class SansStateData(Record):
    astronaut_id: str
    state: SansState
    since_flight_day: int
    retest_due_day: int | None  # modelden gelir; backend üretmez
    last_analysis_id: int


# --- Alarm ve bildirim -------------------------------------------------------------


class AlertCreate(Record):
    astronaut_id: str
    module: AnalysisModule
    severity: Severity
    anomaly_result_id: uuid.UUID | None = None
    sans_analysis_id: int | None = None

    @model_validator(mode="after")
    def _source(self) -> AlertCreate:
        if self.severity is Severity.NORMAL:
            raise ValueError("NORMAL için alarm oluşturulmaz")
        if self.module is AnalysisModule.ANOMALY and (
            self.anomaly_result_id is None or self.sans_analysis_id is not None
        ):
            raise ValueError("anomaly alarmı yalnız anomaly_result_id taşır")
        if self.module is AnalysisModule.SANS and (
            self.sans_analysis_id is None or self.anomaly_result_id is not None
        ):
            raise ValueError("sans alarmı yalnız sans_analysis_id taşır")
        return self


class AlertRecord(Record):
    alert_id: uuid.UUID
    astronaut_id: str
    module: AnalysisModule
    severity: Severity
    status: AlertStatus
    anomaly_result_id: uuid.UUID | None
    sans_analysis_id: int | None
    acknowledged_by: uuid.UUID | None
    acknowledged_at: datetime | None
    resolved_by: uuid.UUID | None
    resolved_at: datetime | None
    resolution_note: str | None
    created_at: datetime


class NotificationEventCreate(Record):
    event_type: EventType
    audience: Audience
    target_user_id: uuid.UUID | None  # ASTRONAUT hedefinde dolu, GROUND_CONTROL'de None
    job_id: uuid.UUID | None = None
    alert_id: uuid.UUID | None = None
    payload: dict[str, Any]

    @model_validator(mode="after")
    def _subject(self) -> NotificationEventCreate:
        if (self.job_id is None) == (self.alert_id is None):
            raise ValueError("olay ya job_id ya alert_id taşır (XOR)")
        if self.event_type is EventType.RISK_ALERT_CREATED and self.alert_id is None:
            raise ValueError("risk.alert.created alert_id ister")
        if self.event_type is EventType.ANALYSIS_COMPLETED and self.job_id is None:
            raise ValueError("analysis.completed job_id ister")
        if (self.audience is Audience.ASTRONAUT) != (self.target_user_id is not None):
            raise ValueError("target_user_id yalnız ASTRONAUT hedefinde dolu")
        if self.audience is Audience.GROUND_CONTROL and self.event_type is not EventType.RISK_ALERT_CREATED:
            raise ValueError("kuleye yalnız risk.alert.created gider")
        return self


class NotificationEventRecord(Record):
    event_id: uuid.UUID
    event_type: EventType
    audience: Audience
    target_user_id: uuid.UUID | None
    job_id: uuid.UUID | None
    alert_id: uuid.UUID | None
    payload: dict[str, Any]
    created_at: datetime
    first_sent_at: datetime | None
    received_at: datetime | None
    attempts: int
