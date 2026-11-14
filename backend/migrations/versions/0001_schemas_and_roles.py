"""A0: altı şema, iki servis rolü, rol üyelikleri ve evaluation DENY

Ön koşul: scripts/bootstrap.py login ve USER'ları oluşturmuş olmalı. Bu migration USER
oluşturmaz; yalnız rolleri ve izin temelini sürümler (şema §8, rev.3).

Tablo/VIEW izinleri burada VERİLMEZ: nesne oluştuğu migration'da (A1-A5)
migrations/helpers.py içindeki grant() ile verilir.

SANS için SQL rolü yoktur (rev.3): SANS veriyi backend'den API ile alır.

Bütün şemalar dbo sahipliğindedir; VIEW'lar sahiplik zinciriyle çalışır.

Revision ID: 0001
Revises:
"""
from alembic import op

from app.db.base import SCHEMAS

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

DML = "SELECT, INSERT, UPDATE, DELETE"

# rol -> bootstrap'in oluşturduğu USER
ROLES = {
    "astra_app_role": "astra_app",
    "astra_eval_role": "astra_eval",
}

# Şema oluştuğu anda tanımlanan açık DENY (şema §8): API/işçi evaluation'a hiç erişemez
DENIES = {
    "astra_app_role": ("evaluation",),
}


def upgrade() -> None:
    for schema in SCHEMAS:
        # CREATE SCHEMA batch'in tek ifadesi olmalı; EXEC ile sarmalanır
        op.execute(
            f"IF SCHEMA_ID(N'{schema}') IS NULL "
            f"EXEC(N'CREATE SCHEMA [{schema}] AUTHORIZATION [dbo]')"
        )

    for role, user in ROLES.items():
        op.execute(
            f"IF DATABASE_PRINCIPAL_ID(N'{role}') IS NULL "
            f"EXEC(N'CREATE ROLE [{role}] AUTHORIZATION [dbo]')"
        )
        # Bootstrap çalışmadıysa sessizce geçmek yerine açık hata ver
        op.execute(
            f"IF USER_ID(N'{user}') IS NULL "
            f"RAISERROR(N'{user} USER bulunamadi: once bootstrap calistirin.', 16, 1)"
        )
        op.execute(
            f"IF IS_ROLEMEMBER(N'{role}', N'{user}') = 0 "
            f"ALTER ROLE [{role}] ADD MEMBER [{user}]"
        )

    for role, schemas in DENIES.items():
        for schema in schemas:
            op.execute(f"DENY {DML} ON SCHEMA::[{schema}] TO [{role}]")


def downgrade() -> None:
    for role, schemas in DENIES.items():
        for schema in schemas:
            op.execute(f"REVOKE {DML} ON SCHEMA::[{schema}] FROM [{role}]")
    for role, user in ROLES.items():
        op.execute(
            f"IF IS_ROLEMEMBER(N'{role}', N'{user}') = 1 "
            f"ALTER ROLE [{role}] DROP MEMBER [{user}]"
        )
        op.execute(f"IF DATABASE_PRINCIPAL_ID(N'{role}') IS NOT NULL DROP ROLE [{role}]")
    for schema in reversed(SCHEMAS):
        op.execute(f"IF SCHEMA_ID(N'{schema}') IS NOT NULL DROP SCHEMA [{schema}]")
