"""A1: core.Missions, core.Astronauts, core.Users + nesne izinleri

Kurallar (şema v5.0 §7):
- Missions: length_days > 0.
- Astronauts: mission_id -> Missions; is_display_only varsayılan 0.
- Users: email UQ; astronaut_id filtreli UQ; rol CHECK; ASTRONAUT <-> astronaut_id CHECK.

astra_app_role izinleri: core tablolarında SELECT/INSERT/UPDATE. DELETE verilmez:
kimlik kayıtları silinmez, hesap is_active=0 ile kapatılır.
astra_eval_role core'a erişmez.

Revision ID: 0002
Revises: 0001
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mssql

from migrations.helpers import APP_ROLE, grant, revoke

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

APP_PERMS = {
    "core.Missions": "SELECT, INSERT, UPDATE",
    "core.Astronauts": "SELECT, INSERT, UPDATE",
    "core.Users": "SELECT, INSERT, UPDATE",
}


def upgrade() -> None:
    op.create_table(
        "Missions",
        sa.Column("mission_id", sa.Unicode(32), nullable=False),
        sa.Column("name", sa.Unicode(256), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("length_days", sa.Integer(), nullable=False),
        sa.Column("scenario", sa.String(10), nullable=True),
        sa.CheckConstraint("length_days > 0", name=op.f("CK_Missions_length_days_positive")),
        sa.PrimaryKeyConstraint("mission_id", name=op.f("PK_Missions")),
        schema="core",
    )

    op.create_table(
        "Astronauts",
        sa.Column("astronaut_id", sa.Unicode(32), nullable=False),
        sa.Column("display_name", sa.Unicode(256), nullable=False),
        sa.Column("mission_id", sa.Unicode(32), nullable=False),
        sa.Column("is_display_only", sa.Boolean(), server_default=sa.text("0"), nullable=False),
        sa.Column("age", sa.SmallInteger(), nullable=True),
        sa.Column("sex", sa.CHAR(1), nullable=True),
        sa.Column("weight_kg", sa.Numeric(6, 2), nullable=True),
        sa.Column("prior_flight", sa.Boolean(), nullable=True),
        sa.Column("prior_sans", sa.Boolean(), nullable=True),
        sa.Column("mtrr66_g", mssql.TINYINT(), nullable=True),
        sa.Column("shmt1_1420_c", mssql.TINYINT(), nullable=True),
        sa.Column("b_vit_status", sa.Numeric(18, 6), nullable=True),
        sa.Column("optic_cup_vol", sa.Numeric(18, 6), nullable=True),
        sa.ForeignKeyConstraint(
            ["mission_id"], ["core.Missions.mission_id"], name=op.f("FK_Astronauts_mission_id")
        ),
        sa.PrimaryKeyConstraint("astronaut_id", name=op.f("PK_Astronauts")),
        schema="core",
    )

    op.create_table(
        "Users",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.Unicode(254), nullable=False),
        sa.Column("password_hash", sa.Unicode(512), nullable=False),
        sa.Column("role", sa.String(40), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.Column(
            "created_at",
            mssql.DATETIME2(precision=3),
            server_default=sa.text("SYSUTCDATETIME()"),
            nullable=False,
        ),
        sa.Column("astronaut_id", sa.Unicode(32), nullable=True),
        sa.CheckConstraint(
            "role IN ('ASTRONAUT','GROUND_CONTROL')", name=op.f("CK_Users_role_valid")
        ),
        sa.CheckConstraint(
            "(role='ASTRONAUT' AND astronaut_id IS NOT NULL)"
            " OR (role='GROUND_CONTROL' AND astronaut_id IS NULL)",
            name=op.f("CK_Users_role_astronaut_link"),
        ),
        sa.ForeignKeyConstraint(
            ["astronaut_id"], ["core.Astronauts.astronaut_id"], name=op.f("FK_Users_astronaut_id")
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("PK_Users")),
        sa.UniqueConstraint("email", name=op.f("UQ_Users_email")),
        schema="core",
    )
    op.create_index(
        "UQ_Users_astronaut_id",
        "Users",
        ["astronaut_id"],
        unique=True,
        schema="core",
        mssql_where=sa.text("astronaut_id IS NOT NULL"),
    )

    for obj, perms in APP_PERMS.items():
        grant(obj, APP_ROLE, perms)


def downgrade() -> None:
    for obj, perms in APP_PERMS.items():
        revoke(obj, APP_ROLE, perms)
    op.drop_index("UQ_Users_astronaut_id", table_name="Users", schema="core")
    op.drop_table("Users", schema="core")
    op.drop_table("Astronauts", schema="core")
    op.drop_table("Missions", schema="core")
