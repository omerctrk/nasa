"""A2: sans şeması — göz modülünün kaynak tabloları (şema v5.0 §7).

Tablo/alan adları SANS kaynağıyla aynı tutulur (oturum, test_kaydi, flight_day…).
flight_day negatif olabilir (uçuş öncesi -60/-30/-10). Tarihler gün hassasiyetindedir;
saat eklenmez. JSON alanları NVARCHAR(MAX) + ISJSON CHECK.
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlalchemy import (
    CHAR,
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Unicode,
    UnicodeText,
    UniqueConstraint,
)
from sqlalchemy.dialects.mssql import DATETIME2
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

ASTRONAUT_FK = "core.Astronauts.astronaut_id"


class Oturum(Base):
    """Göz oturumu. Tekrar test önceki oturuma self-FK ile bağlanır."""

    __tablename__ = "oturum"
    __table_args__ = (
        CheckConstraint("quality_score BETWEEN 0 AND 1", name="quality_score_range"),
        CheckConstraint("checklist_json IS NULL OR ISJSON(checklist_json)=1", name="checklist_json"),
        CheckConstraint("source IN ('synthetic','test_screen','manual')", name="source_valid"),
        CheckConstraint(
            "(is_retest=0 AND retest_of IS NULL)"
            " OR (is_retest=1 AND retest_of IS NOT NULL AND retest_of<>session_id)",
            name="retest_link",
        ),
        {"schema": "sans"},
    )

    session_id: Mapped[str] = mapped_column(Unicode(64), primary_key=True)
    astronaut_id: Mapped[str] = mapped_column(Unicode(32), ForeignKey(ASTRONAUT_FK))
    date: Mapped[dt.date] = mapped_column(Date)
    flight_day: Mapped[int] = mapped_column(Integer)
    is_retest: Mapped[bool] = mapped_column(Boolean)
    retest_of: Mapped[str | None] = mapped_column(
        Unicode(64), ForeignKey("sans.oturum.session_id")
    )
    quality_score: Mapped[Decimal] = mapped_column(Numeric(7, 6))
    checklist_json: Mapped[str | None] = mapped_column(UnicodeText)
    source: Mapped[str] = mapped_column(String(20))


class TestKaydi(Base):
    """Göz testi sonucu; tam oturum = 3 test × 2 göz = 6 satır."""

    __tablename__ = "test_kaydi"
    __test__ = False  # pytest bunu test sınıfı sanmasın
    __table_args__ = (
        UniqueConstraint("session_id", "eye", "test"),
        CheckConstraint("eye IN ('OD','OS')", name="eye_valid"),
        CheckConstraint(
            "(test='near_acuity' AND unit='logMAR') OR (test='contrast' AND unit='logCS')"
            " OR (test='amsler' AND unit='cells')",
            name="test_unit",
        ),
        CheckConstraint("amsler_cells IS NULL OR ISJSON(amsler_cells)=1", name="amsler_cells_json"),
        CheckConstraint(
            "(n_correct IS NULL AND n_presented IS NULL) OR (n_correct IS NOT NULL"
            " AND n_presented IS NOT NULL AND n_correct>=0 AND n_correct<=n_presented)",
            name="counts",
        ),
        CheckConstraint("duration_s IS NULL OR duration_s>=0", name="duration_nonneg"),
        {"schema": "sans"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(Unicode(64), ForeignKey("sans.oturum.session_id"))
    astronaut_id: Mapped[str] = mapped_column(Unicode(32), ForeignKey(ASTRONAUT_FK))
    flight_day: Mapped[int] = mapped_column(Integer)
    eye: Mapped[str] = mapped_column(CHAR(2))
    test: Mapped[str] = mapped_column(String(20))
    value: Mapped[Decimal] = mapped_column(Numeric(18, 6))  # logMAR negatif olabilir
    unit: Mapped[str] = mapped_column(String(10))
    amsler_cells: Mapped[str | None] = mapped_column(UnicodeText)
    n_correct: Mapped[int | None] = mapped_column(Integer)
    n_presented: Mapped[int | None] = mapped_column(Integer)
    duration_s: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))


class Ortam(Base):
    """Görev/gün kabin CO₂ ortalaması."""

    __tablename__ = "ortam"
    __table_args__ = (
        CheckConstraint("co2_mmhg BETWEEN 0 AND 15", name="co2_range"),
        CheckConstraint("source IN ('synthetic','osdr')", name="source_valid"),
        {"schema": "sans"},
    )

    mission_id: Mapped[str] = mapped_column(
        Unicode(32), ForeignKey("core.Missions.mission_id"), primary_key=True
    )
    day: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    co2_mmhg: Mapped[Decimal] = mapped_column(Numeric(7, 4))
    source: Mapped[str] = mapped_column(String(20))


class Semptom(Base):
    """Baş ağrısı kaydı; olmayan güne otomatik taşınmaz."""

    __tablename__ = "semptom"
    __table_args__ = {"schema": "sans"}

    astronaut_id: Mapped[str] = mapped_column(
        Unicode(32), ForeignKey(ASTRONAUT_FK), primary_key=True
    )
    flight_day: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    headache: Mapped[bool] = mapped_column(Boolean)


class Analiz(Base):
    """Göz modelinin SANS risk/seviye/durum sonucu."""

    __tablename__ = "analiz"
    __table_args__ = (
        CheckConstraint("risk BETWEEN 0 AND 1", name="risk_range"),
        CheckConstraint("module='sans'", name="module_sans"),
        CheckConstraint("level IN ('green','yellow','red')", name="level_valid"),
        CheckConstraint("state IN ('normal','suspect','confirmed')", name="state_valid"),
        CheckConstraint("drivers_json IS NULL OR ISJSON(drivers_json)=1", name="drivers_json"),
        CheckConstraint("trend_json IS NULL OR ISJSON(trend_json)=1", name="trend_json"),
        {"schema": "sans"},
    )

    analysis_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    astronaut_id: Mapped[str] = mapped_column(Unicode(32), ForeignKey(ASTRONAUT_FK))
    session_id: Mapped[str | None] = mapped_column(
        Unicode(64), ForeignKey("sans.oturum.session_id")
    )
    flight_day: Mapped[int] = mapped_column(Integer)
    # Şemada varsayılan yok (import kaynağın zamanını korur); canlı kayıtta repository
    # SYSUTCDATETIME() yazar.
    created_at: Mapped[dt.datetime] = mapped_column(DATETIME2(3))
    module: Mapped[str] = mapped_column(String(24))
    risk: Mapped[Decimal] = mapped_column(Numeric(7, 6))
    level: Mapped[str] = mapped_column(String(10))
    state: Mapped[str] = mapped_column(String(12))
    summary: Mapped[str | None] = mapped_column(Unicode(4000))
    recommendation: Mapped[str | None] = mapped_column(Unicode(2000))
    drivers_json: Mapped[str | None] = mapped_column(UnicodeText)
    trend_json: Mapped[str | None] = mapped_column(UnicodeText)
    model_version: Mapped[str | None] = mapped_column(Unicode(100))


class Durum(Base):
    """Göz modülünün astronot başına güncel durumu."""

    __tablename__ = "durum"
    __table_args__ = (
        CheckConstraint("state IN ('normal','suspect','confirmed')", name="state_valid"),
        {"schema": "sans"},
    )

    astronaut_id: Mapped[str] = mapped_column(
        Unicode(32), ForeignKey(ASTRONAUT_FK), primary_key=True
    )
    state: Mapped[str] = mapped_column(String(12))
    since_flight_day: Mapped[int] = mapped_column(Integer)
    retest_due_day: Mapped[int | None] = mapped_column(Integer)
    last_analysis_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("sans.analiz.analysis_id")
    )
