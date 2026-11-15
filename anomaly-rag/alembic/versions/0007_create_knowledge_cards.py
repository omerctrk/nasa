"""Create durable Knowledge Card storage.

Revision ID: 0007
Revises: 0006
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mssql


# revision identifiers, used by Alembic.
revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

SCHEMA = "dbo"
TABLE = "knowledge_cards"


def _verify_application_principal_configuration() -> None:
    """Fail before DDL if the existing application role setup is incomplete.

    This does not create a role, grant membership, or grant directly to the
    application user. The privileged migration service must apply the intended
    central database configuration first.
    """
    op.execute(
        sa.text(
            """
            IF NOT EXISTS (
                SELECT 1
                FROM sys.database_principals
                WHERE name = N'astra_app_role' AND type = 'R'
            )
                THROW 51000, 'Required database role astra_app_role does not exist.', 1;

            IF NOT EXISTS (
                SELECT 1
                FROM sys.database_role_members AS membership
                INNER JOIN sys.database_principals AS role_principal
                    ON role_principal.principal_id = membership.role_principal_id
                INNER JOIN sys.database_principals AS member_principal
                    ON member_principal.principal_id = membership.member_principal_id
                WHERE role_principal.name = N'astra_app_role'
                  AND member_principal.name = N'astra_collaborator'
            )
                THROW 51001,
                    'astra_collaborator is not a member of astra_app_role; migration aborted without changing role membership.',
                    1;
            """
        )
    )


def upgrade() -> None:
    _verify_application_principal_configuration()
    op.create_table(
        TABLE,
        sa.Column("card_id", sa.Unicode(length=80), nullable=False),
        sa.Column("type", sa.Unicode(length=32), nullable=False),
        sa.Column("system", sa.Unicode(length=64), nullable=False),
        sa.Column(
            "metrics",
            sa.UnicodeText().with_variant(mssql.NVARCHAR(length=None), "mssql"),
            nullable=False,
        ),
        sa.Column("direction", sa.Unicode(length=16), nullable=False),
        sa.Column(
            "text",
            sa.UnicodeText().with_variant(mssql.NVARCHAR(length=None), "mssql"),
            nullable=False,
        ),
        sa.Column("source", sa.Unicode(length=500), nullable=False),
        sa.Column("url", sa.Unicode(length=2048), nullable=False),
        sa.Column("locator", sa.Unicode(length=500), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime().with_variant(mssql.DATETIME2(), "mssql"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime().with_variant(mssql.DATETIME2(), "mssql"),
            nullable=False,
        ),
        sa.CheckConstraint("ISJSON(metrics) = 1", name="ck_knowledge_cards_metrics_json"),
        sa.PrimaryKeyConstraint("card_id", name="pk_knowledge_cards"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_knowledge_cards_content_hash",
        TABLE,
        ["content_hash"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index("ix_knowledge_cards_system", TABLE, ["system"], unique=False, schema=SCHEMA)
    op.execute(
        sa.text(
            """
            GRANT SELECT, INSERT, UPDATE, DELETE
            ON OBJECT::dbo.knowledge_cards
            TO [astra_app_role];
            """
        )
    )


def downgrade() -> None:
    # Revoke only privileges introduced by this migration; never alter role membership.
    op.execute(
        sa.text(
            """
            IF EXISTS (
                SELECT 1
                FROM sys.database_principals
                WHERE name = N'astra_app_role' AND type = 'R'
            )
            BEGIN
                REVOKE SELECT, INSERT, UPDATE, DELETE
                ON OBJECT::dbo.knowledge_cards
                FROM [astra_app_role];
            END;
            """
        )
    )
    op.drop_index("ix_knowledge_cards_system", table_name=TABLE, schema=SCHEMA)
    op.drop_index("ix_knowledge_cards_content_hash", table_name=TABLE, schema=SCHEMA)
    op.drop_table(TABLE, schema=SCHEMA)
