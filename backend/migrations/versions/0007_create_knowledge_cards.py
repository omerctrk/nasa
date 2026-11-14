"""Create dbo.knowledge_cards.

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-14

This migration is intended for the AstraHealth SQL Server database.
It creates only dbo.knowledge_cards and grants data permissions to
astra_app_role. It does not create roles or change role membership.
"""

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import mssql

from migrations.helpers import APP_ROLE, grant, revoke


revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


TABLE_NAME = "knowledge_cards"
SCHEMA_NAME = "dbo"


def _preflight(bind) -> None:
    """Fail before DDL if the expected schema or role is absent."""
    if context.is_offline_mode():
        return  # Offline SQL generation has no live database to query.
    checks = bind.execute(
        sa.text(
            """
            SELECT
                CASE WHEN SCHEMA_ID(:schema_name) IS NOT NULL THEN 1 ELSE 0 END
                    AS schema_exists,
                CASE WHEN EXISTS (
                    SELECT 1
                    FROM sys.database_principals
                    WHERE name = :role_name AND type = 'R'
                ) THEN 1 ELSE 0 END AS role_exists
            """
        ),
        {"schema_name": SCHEMA_NAME, "role_name": APP_ROLE},
    ).mappings().one()

    missing = []
    if not checks["schema_exists"]:
        missing.append("dbo schema")
    if not checks["role_exists"]:
        missing.append(APP_ROLE + " database role")
    if missing:
        raise RuntimeError(
            "Migration 0007 preflight failed; missing: " + ", ".join(missing)
        )


def upgrade() -> None:
    bind = op.get_bind()
    _preflight(bind)

    op.create_table(
        TABLE_NAME,
        sa.Column("card_id", sa.NVARCHAR(length=80), primary_key=True, nullable=False),
        sa.Column("type", sa.NVARCHAR(length=32), nullable=False),
        sa.Column("system", sa.NVARCHAR(length=64), nullable=False),
        sa.Column("metrics", sa.NVARCHAR(length=None), nullable=False),
        sa.Column("direction", sa.NVARCHAR(length=16), nullable=False),
        sa.Column("text", sa.NVARCHAR(length=None), nullable=False),
        sa.Column("source", sa.NVARCHAR(length=512), nullable=False),
        sa.Column("url", sa.NVARCHAR(length=2048), nullable=False),
        sa.Column("locator", sa.NVARCHAR(length=512), nullable=False),
        sa.Column("content_hash", sa.VARCHAR(length=64), nullable=False),
        sa.Column(
            "created_at",
            mssql.DATETIME2(),
            nullable=False,
            server_default=sa.text("SYSUTCDATETIME()"),
        ),
        sa.Column(
            "updated_at",
            mssql.DATETIME2(),
            nullable=False,
            server_default=sa.text("SYSUTCDATETIME()"),
        ),
        sa.CheckConstraint("ISJSON([metrics]) = 1", name="ck_knowledge_cards_metrics_json"),
        schema=SCHEMA_NAME,
    )

    op.create_index(
        "ix_knowledge_cards_content_hash",
        TABLE_NAME,
        ["content_hash"],
        unique=False,
        schema=SCHEMA_NAME,
    )

    # This content table explicitly supports deletion; all existing clinical
    # and operational tables retain their no-DELETE rule.
    grant("dbo.knowledge_cards", APP_ROLE, "SELECT, INSERT, UPDATE, DELETE")


def downgrade() -> None:
    revoke("dbo.knowledge_cards", APP_ROLE, "SELECT, INSERT, UPDATE, DELETE")
    op.drop_index(
        "ix_knowledge_cards_content_hash",
        table_name=TABLE_NAME,
        schema=SCHEMA_NAME,
    )
    op.drop_table(TABLE_NAME, schema=SCHEMA_NAME)
