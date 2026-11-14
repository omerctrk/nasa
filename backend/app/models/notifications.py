"""A3: ops.Alerts, ops.NotificationEvents, ops.EventReceipts (şema v5.0 §7).

- Alerts: kule operatörünün OPEN → ACKNOWLEDGED → RESOLVED akışı; model sonucu başına tek alarm.
- NotificationEvents: kalıcı gönderim kaydı (outbox); konu job_id XOR alert_id.
- EventReceipts: ekranın teknik teslim alındısı — insan onayı DEĞİL.
"""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Unicode,
    UnicodeText,
    Uuid,
    text,
)
from sqlalchemy.dialects.mssql import DATETIME2
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

USER_FK = "core.Users.user_id"


class Alert(Base):
    __tablename__ = "Alerts"
    __table_args__ = (
        CheckConstraint("status IN ('OPEN','ACKNOWLEDGED','RESOLVED')", name="status_valid"),
        CheckConstraint(
            "(status='OPEN' AND acknowledged_by IS NULL AND acknowledged_at IS NULL)"
            " OR (status IN ('ACKNOWLEDGED','RESOLVED') AND acknowledged_by IS NOT NULL"
            " AND acknowledged_at IS NOT NULL)",
            name="ack_by_status",
        ),
        CheckConstraint(
            "(status<>'RESOLVED' AND resolved_by IS NULL AND resolved_at IS NULL"
            " AND resolution_note IS NULL) OR (status='RESOLVED' AND resolved_by IS NOT NULL"
            " AND resolved_at IS NOT NULL AND resolved_at >= acknowledged_at"
            " AND resolution_note IS NOT NULL AND LEN(LTRIM(RTRIM(resolution_note)))>0)",
            name="resolve_by_status",
        ),
        CheckConstraint(
            "(module='anomaly' AND anomaly_result_id IS NOT NULL AND sans_analysis_id IS NULL)"
            " OR (module='sans' AND sans_analysis_id IS NOT NULL AND anomaly_result_id IS NULL)",
            name="source_by_module",
        ),
        CheckConstraint("severity IN ('WARNING','CRITICAL')", name="severity_valid"),
        Index(
            "UQ_Alerts_anomaly_result_id", "anomaly_result_id", unique=True,
            mssql_where=text("anomaly_result_id IS NOT NULL"),
        ),
        Index(
            "UQ_Alerts_sans_analysis_id", "sans_analysis_id", unique=True,
            mssql_where=text("sans_analysis_id IS NOT NULL"),
        ),
        {"schema": "ops"},
    )

    alert_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    status: Mapped[str] = mapped_column(String(40), server_default=text("'OPEN'"))
    acknowledged_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey(USER_FK))
    acknowledged_at: Mapped[dt.datetime | None] = mapped_column(DATETIME2(3))
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey(USER_FK))
    resolved_at: Mapped[dt.datetime | None] = mapped_column(DATETIME2(3))
    resolution_note: Mapped[str | None] = mapped_column(Unicode(1000))
    created_at: Mapped[dt.datetime] = mapped_column(
        DATETIME2(3), server_default=text("SYSUTCDATETIME()")
    )
    astronaut_id: Mapped[str] = mapped_column(
        Unicode(32), ForeignKey("core.Astronauts.astronaut_id")
    )
    module: Mapped[str] = mapped_column(String(24))
    anomaly_result_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("anomaly.anomaly_results.id")
    )
    sans_analysis_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("sans.analiz.analysis_id")
    )
    severity: Mapped[str] = mapped_column(String(10))


class NotificationEvent(Base):
    __tablename__ = "NotificationEvents"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('analysis.completed','risk.alert.created')", name="event_type_valid"
        ),
        CheckConstraint("audience IN ('ASTRONAUT','GROUND_CONTROL')", name="audience_valid"),
        CheckConstraint(
            "(audience='ASTRONAUT' AND target_user_id IS NOT NULL)"
            " OR (audience='GROUND_CONTROL' AND target_user_id IS NULL)",
            name="target_by_audience",
        ),
        CheckConstraint(
            "audience <> 'GROUND_CONTROL' OR event_type='risk.alert.created'",
            name="ground_only_risk",
        ),
        CheckConstraint("ISJSON(payload_json)=1", name="payload_json"),
        CheckConstraint("attempts >= 0", name="attempts_nonneg"),
        CheckConstraint(
            "(job_id IS NOT NULL AND alert_id IS NULL) OR (job_id IS NULL AND alert_id IS NOT NULL)",
            name="subject_xor",
        ),
        CheckConstraint(
            "(event_type='risk.alert.created' AND alert_id IS NOT NULL)"
            " OR (event_type='analysis.completed' AND job_id IS NOT NULL)",
            name="subject_by_type",
        ),
        Index(
            "UQ_NotificationEvents_alert_id_audience", "alert_id", "audience", unique=True,
            mssql_where=text("alert_id IS NOT NULL"),
        ),
        Index(
            "UQ_NotificationEvents_job_id_audience", "job_id", "audience", unique=True,
            mssql_where=text("job_id IS NOT NULL"),
        ),
        {"schema": "ops"},
    )

    event_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("ops.AnalysisJobs.job_id"))
    alert_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("ops.Alerts.alert_id"))
    event_type: Mapped[str] = mapped_column(String(40))
    audience: Mapped[str] = mapped_column(String(40))
    target_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey(USER_FK))
    payload_json: Mapped[str] = mapped_column(UnicodeText)
    created_at: Mapped[dt.datetime] = mapped_column(
        DATETIME2(3), server_default=text("SYSUTCDATETIME()")
    )
    first_sent_at: Mapped[dt.datetime | None] = mapped_column(DATETIME2(3))
    received_at: Mapped[dt.datetime | None] = mapped_column(DATETIME2(3))
    next_attempt_at: Mapped[dt.datetime] = mapped_column(
        DATETIME2(3), server_default=text("SYSUTCDATETIME()")
    )
    attempts: Mapped[int] = mapped_column(Integer, server_default=text("0"))


class EventReceipt(Base):
    __tablename__ = "EventReceipts"
    __table_args__ = {"schema": "ops"}

    event_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("ops.NotificationEvents.event_id"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey(USER_FK), primary_key=True)
    received_at: Mapped[dt.datetime] = mapped_column(
        DATETIME2(3), server_default=text("SYSUTCDATETIME()")
    )
