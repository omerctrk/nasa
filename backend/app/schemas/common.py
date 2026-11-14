"""Ortak sözleşme (Aybala + Ömer): enum'lar, hata zarfı, CurrentUser, ortak ölçüm DTO'su.

Ayrıntılı açıklama: contracts/backend-contract.md. Bu dosyadaki bir değeri değiştirmek
sözleşme değişikliğidir; ikinizin onayıyla ve fixture'larla birlikte yapılır.

Enum değerleri DB CHECK değerleriyle birebir aynıdır; büyük/küçük harf dönüşümü yapılmaz.
"""
from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, field_validator, model_validator

API_PREFIX = "/api/v1"
WS_NOTIFICATIONS_PATH = "/ws/v1/notifications"


# --- Enum'lar (sözleşme §2) -------------------------------------------------------


class Role(StrEnum):
    ASTRONAUT = "ASTRONAUT"
    GROUND_CONTROL = "GROUND_CONTROL"


class JobState(StrEnum):
    QUEUED = "QUEUED"
    SYNCING = "SYNCING"
    ANALYZING = "ANALYZING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class AlertStatus(StrEnum):
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"


class Severity(StrEnum):
    """NORMAL yalnız ekranda; ops.Alerts'e yalnız WARNING/CRITICAL yazılır."""

    NORMAL = "NORMAL"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class AnomalyLevel(StrEnum):
    NORMAL = "normal"
    WATCH = "watch"
    REVIEW = "review"


class SansLevel(StrEnum):
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"


class SansState(StrEnum):
    NORMAL = "normal"
    SUSPECT = "suspect"
    CONFIRMED = "confirmed"


class AnalysisModule(StrEnum):
    """Analizi YAPAN modül (job, sonuç, alarm)."""

    ANOMALY = "anomaly"
    SANS = "sans"


class MeasurementModule(StrEnum):
    """Ölçümün GELDİĞİ modül (ortak ölçüm DTO'su, MeasurementDefinitions)."""

    PHYSIOLOGICAL = "physiological"
    BEHAVIORAL = "behavioral"
    SANS = "sans"


class Source(StrEnum):
    """Ortak DTO kaynağı. Kaynak tablodaki seed -> synthetic, test_screen -> manual;
    orijinal değer metadata_json.original_source içinde korunur."""

    MANUAL = "manual"
    SYNTHETIC = "synthetic"


class Eye(StrEnum):
    OD = "OD"  # sağ
    OS = "OS"  # sol


class TimePrecision(StrEnum):
    DATE = "date"
    TIMESTAMP = "timestamp"


class EvaluationStatus(StrEnum):
    EVALUATED = "evaluated"
    INSUFFICIENT_DATA = "insufficient_data"
    INVALID_DATA = "invalid_data"


# --- Şemadaki diğer CHECK değerleri (repository kayıtları bunları kullanır) ---------


class ModuleScope(StrEnum):
    PHYSIOLOGICAL = "physiological"
    BEHAVIORAL = "behavioral"
    SANS = "sans"
    COMBINED = "combined"


class BaselineStatus(StrEnum):
    INSUFFICIENT_DATA = "insufficient_data"
    PROVISIONAL = "provisional"
    READY = "ready"


class DataQualityStatus(StrEnum):
    VALID = "valid"
    LOW_QUALITY = "low_quality"
    MISSING_DATA = "missing_data"


class EventType(StrEnum):
    ANALYSIS_COMPLETED = "analysis.completed"
    RISK_ALERT_CREATED = "risk.alert.created"


class Audience(StrEnum):
    ASTRONAUT = "ASTRONAUT"
    GROUND_CONTROL = "GROUND_CONTROL"


# --- Temel modeller ---------------------------------------------------------------


class ContractModel(BaseModel):
    """Bütün istek/yanıt modellerinin tabanı: bilinmeyen alan reddedilir (§4)."""

    model_config = ConfigDict(extra="forbid")


# API'de JSON number, Python/DB tarafında Decimal (§3).
JsonDecimal = Annotated[Decimal, PlainSerializer(float, return_type=float, when_used="json")]


class CurrentUser(ContractModel):
    """Ömer'in yetki dependency'lerinin döndürdüğü kullanıcı (§5).

    current_user() / require_active_astronaut() / require_ground_control()
    """

    user_id: uuid.UUID
    role: Role
    astronaut_id: str | None


# --- Hata zarfı (§4) -------------------------------------------------------------


class ErrorCode(StrEnum):
    UNAUTHORIZED = "UNAUTHORIZED"  # 401
    FORBIDDEN = "FORBIDDEN"  # 403
    NOT_FOUND = "NOT_FOUND"  # 404
    IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"  # 409
    INVALID_STATE_TRANSITION = "INVALID_STATE_TRANSITION"  # 409
    PRECONDITION_FAILED = "PRECONDITION_FAILED"  # 412
    VALIDATION_ERROR = "VALIDATION_ERROR"  # 422
    INTERNAL_ERROR = "INTERNAL_ERROR"  # 500


class ErrorField(ContractModel):
    field: str
    code: str  # ör. INVALID_VALUE, REQUIRED, UNKNOWN_FIELD
    message: str


class ErrorBody(ContractModel):
    code: ErrorCode
    message: str
    trace_id: uuid.UUID
    fields: list[ErrorField] = Field(default_factory=list)


class ErrorResponse(ContractModel):
    """Bütün hata yanıtları: {"detail": {...}}. SQL, token, parola, ham model çıktısı
    veya sağlık girdisinin tamamı burada bulunmaz."""

    detail: ErrorBody


# --- Ortak ölçüm DTO'su (§3) -----------------------------------------------------


class MeasurementDTO(ContractModel):
    """Aybala üretir (VIEW/tablolardan), Ömer geçmiş/snapshot/model hazırlığında tüketir."""

    record_id: str = Field(min_length=1, max_length=200)  # ör. "checkin:12:stress", "eye:42"
    astronaut_id: str
    mission_id: str
    module: MeasurementModule
    measurement: str
    value_num: JsonDecimal | None = None
    value_text: str | None = None
    unit: str
    protocol_version: str = Field(min_length=1)
    measured_date: date
    measured_at: datetime | None = None
    time_precision: TimePrecision
    mission_day: int | None = None  # negatif olabilir (uçuş öncesi)
    eye: Eye | None = None
    source: Source
    valid: bool
    quality_score: JsonDecimal | None = Field(default=None, ge=0, le=1)
    session_id: str | None = None
    metadata_json: dict[str, Any] | None = None  # JSON nesnesi; JSON içeren metin değil

    @field_validator("measured_at")
    @classmethod
    def _utc(cls, v: datetime | None) -> datetime | None:
        if v is None:
            return v
        if v.tzinfo is None or v.utcoffset() is None:
            raise ValueError("measured_at saat dilimi içermeli (UTC, 'Z')")
        return v.astimezone(UTC)

    @model_validator(mode="after")
    def _rules(self) -> MeasurementDTO:
        if self.time_precision is TimePrecision.DATE and self.measured_at is not None:
            raise ValueError("time_precision=date ise measured_at null olmalı")
        if self.time_precision is TimePrecision.TIMESTAMP:
            if self.measured_at is None:
                raise ValueError("time_precision=timestamp ise measured_at zorunlu")
            if self.measured_at.date() != self.measured_date:
                raise ValueError("measured_date, measured_at'in UTC tarihi olmalı")
        if self.value_num is not None and self.value_text is not None:
            raise ValueError("value_num ve value_text aynı anda dolu olamaz")
        if self.valid and self.value_num is None and self.value_text is None:
            raise ValueError("geçerli ölçümde value_num veya value_text bulunmalı")
        if self.module is not MeasurementModule.SANS and self.eye is not None:
            raise ValueError("göz dışı ölçümde eye null olmalı")
        return self
