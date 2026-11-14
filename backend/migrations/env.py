"""Alembic ortamı. Yalnız `migrate` servisi (sa hesabı) çalıştırır; API çalıştırmaz."""
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine

import app.models  # noqa: F401  tüm modelleri tek metadata'ya kaydeder
from app.core.config import get_settings
from app.db.base import SCHEMAS, Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def include_name(name, type_, parent_names):
    # Autogenerate yalnız bizim altı şemamıza bakar (dbo, sys vb. hariç)
    if type_ == "schema":
        return name in SCHEMAS
    return True


def _configure(**kwargs):
    context.configure(
        target_metadata=target_metadata,
        include_schemas=True,
        include_name=include_name,
        compare_type=True,
        **kwargs,
    )


def run_migrations_offline() -> None:
    """`alembic upgrade head --sql`: DB'ye bağlanmadan T-SQL scripti üretir (inceleme için)."""
    _configure(url=get_settings().database_url, literal_binds=True)
    # Offline modda sunucu sürümü bilinmez; SQLAlchemy 2008 öncesi varsayar ve DATE'i
    # DATETIME yazar. Hedefimiz SQL Server 2022 (16.x) olduğu için sürümü sabitliyoruz.
    dialect = context.get_context().dialect
    dialect.server_version_info = (16, 0)
    dialect._setup_version_attributes()
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(get_settings().database_url)
    with engine.connect() as connection:
        _configure(connection=connection)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
