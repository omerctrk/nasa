"""A1: core.Missions, core.Astronauts, core.Users (şema v5.0 §7).

Zamanlar UTC tutulur. Görev günü (flight_day) Missions.start_date'e göre hesaplanır:
gün 0 = start_date; uçuş öncesi oturumlar negatif gündür (-60, -30, -10).
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import (
    CHAR,
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Unicode,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.mssql import DATETIME2, TINYINT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Mission(Base):
    """Bir görev; görev günü sıfırın tarihini tanımlar."""

    __tablename__ = "Missions"
    __table_args__ = (
        CheckConstraint("length_days > 0", name="length_days_positive"),
        {"schema": "core"},
    )

    mission_id: Mapped[str] = mapped_column(Unicode(32), primary_key=True)
    name: Mapped[str] = mapped_column(Unicode(256))
    start_date: Mapped[date] = mapped_column(Date)
    length_days: Mapped[int] = mapped_column(Integer)
    scenario: Mapped[str | None] = mapped_column(String(10))

    astronauts: Mapped[list[Astronaut]] = relationship(back_populates="mission")

    def flight_day(self, on: date) -> int:
        """Takvim tarihini görev gününe çevirir (gün 0 = start_date)."""
        return (on - self.start_date).days

    def date_for_day(self, flight_day: int) -> date:
        """Görev gününü takvim tarihine çevirir; negatif gün geçerlidir."""
        return self.start_date + timedelta(days=flight_day)


class Astronaut(Base):
    """Ortak astronot kimliği ve görev kaydı. is_display_only=1 profil veri girmez.

    SANS kaynaklı başlangıç alanları (age, sex, genetik, z-skorları) nullable'dır;
    aralık doğrulaması servis katmanında yapılır (şema bu alanlara CHECK koymaz).
    """

    __tablename__ = "Astronauts"
    __table_args__ = {"schema": "core"}

    astronaut_id: Mapped[str] = mapped_column(Unicode(32), primary_key=True)
    display_name: Mapped[str] = mapped_column(Unicode(256))
    mission_id: Mapped[str] = mapped_column(Unicode(32), ForeignKey("core.Missions.mission_id"))
    is_display_only: Mapped[bool] = mapped_column(Boolean, server_default=text("0"))

    age: Mapped[int | None] = mapped_column(SmallInteger)
    sex: Mapped[str | None] = mapped_column(CHAR(1))
    weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    prior_flight: Mapped[bool | None] = mapped_column(Boolean)
    prior_sans: Mapped[bool | None] = mapped_column(Boolean)
    mtrr66_g: Mapped[int | None] = mapped_column(TINYINT)
    shmt1_1420_c: Mapped[int | None] = mapped_column(TINYINT)
    b_vit_status: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    optic_cup_vol: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))

    mission: Mapped[Mission] = relationship(back_populates="astronauts")
    user: Mapped[User | None] = relationship(back_populates="astronaut")


class User(Base):
    """Giriş hesabı. ASTRONAUT kendi astronotuna bağlıdır; GROUND_CONTROL bağlı değildir."""

    __tablename__ = "Users"
    __table_args__ = (
        UniqueConstraint("email"),
        CheckConstraint("role IN ('ASTRONAUT','GROUND_CONTROL')", name="role_valid"),
        CheckConstraint(
            "(role='ASTRONAUT' AND astronaut_id IS NOT NULL)"
            " OR (role='GROUND_CONTROL' AND astronaut_id IS NULL)",
            name="role_astronaut_link",
        ),
        # Filtreli UQ: bir astronotun en fazla bir hesabı olur; kule hesapları NULL.
        Index(
            "UQ_Users_astronaut_id",
            "astronaut_id",
            unique=True,
            mssql_where=text("astronaut_id IS NOT NULL"),
        ),
        {"schema": "core"},
    )

    # UUID uygulamada üretilir (şema §7).
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(Unicode(254))
    password_hash: Mapped[str] = mapped_column(Unicode(512))
    role: Mapped[str] = mapped_column(String(40))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("1"))
    created_at: Mapped[datetime] = mapped_column(
        DATETIME2(3), server_default=text("SYSUTCDATETIME()")
    )
    astronaut_id: Mapped[str | None] = mapped_column(
        Unicode(32), ForeignKey("core.Astronauts.astronaut_id")
    )

    astronaut: Mapped[Astronaut | None] = relationship(back_populates="user")
