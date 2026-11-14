"""Engine ve Session.

Kural (iş bölümü §5): repository kendi başına commit yapmaz; commit servis sınırında yapılır.
Model/API beklerken transaction açık tutulmaz.
"""
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

engine = create_engine(get_settings().database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """FastAPI dependency: her istek kendi Session'ını alır, sonunda kapanır."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
