"""A1 kabul: kimlik/FK/rol kuralları ve M01 tarih eşlemesi (DB gerektirmez)."""
import re
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy.dialects import mssql
from sqlalchemy.schema import CreateIndex, CreateTable

from app.db.base import Base
from app.models import Astronaut, Mission, User
from app.schemas.common import Role

MIGRATION = Path(__file__).parents[2] / "migrations/versions/0002_core_identity.py"


def sql2022():
    d = mssql.dialect()
    d.server_version_info = (16, 0)
    d._setup_version_attributes()
    return d


def ddl(model) -> str:
    return str(CreateTable(model.__table__).compile(dialect=sql2022()))


@pytest.fixture
def m01() -> Mission:
    return Mission(mission_id="M01", name="M01", start_date=date(2027, 1, 5), length_days=180)


def test_core_tables_registered():
    assert {"core.Missions", "core.Astronauts", "core.Users"} <= set(Base.metadata.tables)


@pytest.mark.parametrize(
    ("day", "expected"),
    [(0, date(2027, 1, 5)), (-60, date(2026, 11, 6)), (73, date(2027, 3, 19)),
     (74, date(2027, 3, 20)), (76, date(2027, 3, 22))],
)
def test_m01_day_mapping(m01, day, expected):
    assert m01.date_for_day(day) == expected
    assert m01.flight_day(expected) == day


def test_mssql_types():
    users = ddl(User)
    assert "user_id UNIQUEIDENTIFIER NOT NULL" in users
    assert "created_at DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME()" in users
    assert "email NVARCHAR(254) NOT NULL" in users
    assert "role VARCHAR(40) NOT NULL" in users
    astronauts = ddl(Astronaut)
    assert "is_display_only BIT NOT NULL DEFAULT 0" in astronauts
    assert "mtrr66_g TINYINT NULL" in astronauts
    assert "weight_kg NUMERIC(6, 2) NULL" in astronauts
    assert "sex CHAR(1) NULL" in astronauts
    assert "scenario VARCHAR(10) NULL" in ddl(Mission)
    assert "start_date DATE NOT NULL" in ddl(Mission)


def test_constraints_and_filtered_unique():
    users = ddl(User)
    assert "CONSTRAINT [UQ_Users_email] UNIQUE (email)" in users
    assert "CONSTRAINT [CK_Users_role_valid]" in users
    assert "CONSTRAINT [CK_Users_role_astronaut_link]" in users
    assert "FOREIGN KEY(astronaut_id) REFERENCES core.[Astronauts] (astronaut_id)" in users
    assert "CONSTRAINT [CK_Missions_length_days_positive] CHECK (length_days > 0)" in ddl(Mission)
    (index,) = User.__table__.indexes
    idx = str(CreateIndex(index).compile(dialect=sql2022()))
    assert idx.startswith("CREATE UNIQUE INDEX [UQ_Users_astronaut_id]")
    assert "WHERE astronaut_id IS NOT NULL" in idx


def test_migration_uses_same_constraint_names_as_models():
    model_names = {
        c.name for t in (Mission, Astronaut, User) for c in t.__table__.constraints
    } | {i.name for i in User.__table__.indexes}
    text = MIGRATION.read_text()
    migration_names = set(re.findall(r'"((?:PK|FK|UQ|CK)_[A-Za-z_]+)"', text))
    assert model_names == migration_names


def test_app_role_gets_no_delete_on_core():
    text = MIGRATION.read_text()
    assert "DELETE" not in text.split("APP_PERMS = {")[1].split("}")[0]


def test_role_enum_matches_check():
    assert {r.value for r in Role} == {"ASTRONAUT", "GROUND_CONTROL"}
