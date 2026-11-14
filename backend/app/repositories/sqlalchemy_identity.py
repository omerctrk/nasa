"""IdentityRepository'nin gerçek SQLAlchemy uygulaması (A1, sahip: Aybala).

ORM nesneleri dışarı çıkmaz; records.py modellerine çevrilir. Commit yapılmaz.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.identity import Astronaut, User
from app.repositories.records import AstronautRecord, UserRecord
from app.schemas.common import Role


def normalize_email(email: str) -> str:
    return email.strip().lower()


def _user(row: User) -> UserRecord:
    return UserRecord(
        user_id=row.user_id,
        email=row.email,
        password_hash=row.password_hash,
        role=Role(row.role),
        is_active=row.is_active,
        astronaut_id=row.astronaut_id,
        created_at=row.created_at,
    )


def _astronaut(row: Astronaut) -> AstronautRecord:
    return AstronautRecord(
        astronaut_id=row.astronaut_id,
        display_name=row.display_name,
        mission_id=row.mission_id,
        mission_start_date=row.mission.start_date,
        mission_length_days=row.mission.length_days,
        is_display_only=row.is_display_only,
        age=row.age,
        sex=row.sex,
        weight_kg=row.weight_kg,
        prior_flight=row.prior_flight,
        prior_sans=row.prior_sans,
        mtrr66_g=row.mtrr66_g,
        shmt1_1420_c=row.shmt1_1420_c,
        b_vit_status=row.b_vit_status,
        optic_cup_vol=row.optic_cup_vol,
    )


class SqlAlchemyIdentityRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_user_by_email(self, email: str) -> UserRecord | None:
        row = self.session.scalars(
            select(User).where(User.email == normalize_email(email))
        ).one_or_none()
        return _user(row) if row else None

    def get_user_by_id(self, user_id: uuid.UUID) -> UserRecord | None:
        row = self.session.get(User, user_id)
        return _user(row) if row else None

    def get_user_for_astronaut(self, astronaut_id: str) -> uuid.UUID | None:
        """Astronotun etkin hesabı (Users.astronaut_id filtreli UNIQUE: en fazla bir)."""
        return self.session.scalar(
            select(User.user_id).where(User.astronaut_id == astronaut_id, User.is_active == True)  # noqa: E712 (SQL Server: "= 1"; "IS 1" geçersiz)
        )

    def get_astronaut(self, astronaut_id: str) -> AstronautRecord | None:
        row = self.session.scalars(
            select(Astronaut)
            .options(joinedload(Astronaut.mission))
            .where(Astronaut.astronaut_id == astronaut_id)
        ).one_or_none()
        return _astronaut(row) if row else None
