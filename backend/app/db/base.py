"""Tek Base / tek metadata (iş bölümü §5 "Katman sınırı").

Bütün ORM modelleri bu Base'den türer; Alembic autogenerate yalnız bu metadata'yı görür.
"""
from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# Kısıt adları sabit olsun ki Alembic her seferinde aynı adı üretsin
NAMING_CONVENTION = {
    "pk": "PK_%(table_name)s",
    "fk": "FK_%(table_name)s_%(column_0_N_name)s",
    "uq": "UQ_%(table_name)s_%(column_0_N_name)s",
    "ix": "IX_%(table_name)s_%(column_0_N_name)s",
    "ck": "CK_%(table_name)s_%(constraint_name)s",
}

# Şema v5.0'daki altı SQL şeması (tek AstraHealth veritabanı içinde)
SCHEMAS = ("core", "behavioral", "sans", "anomaly", "ops", "evaluation")


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
