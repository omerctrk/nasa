"""M01: deployed mission-day baseline revision.

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-15

The production AstraHealth database was already stamped at revision 0008, but
the migration artifact was not present in the version1 source tree. A live
schema comparison against a clean 0007 database found no table, column, or
view drift. This revision deliberately performs no DDL; it makes a fresh
version1 installation reach the same verified Alembic revision before a
portable data package is imported.
"""

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
