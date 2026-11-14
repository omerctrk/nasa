"""Engine ve Session.

Kural (iş bölümü §5): repository kendi başına commit yapmaz; commit servis sınırında yapılır.
Model/API beklerken transaction açık tutulmaz.

Engine ilk kullanımda oluşturulur: uygulama/araçlar DB ayarı olmadan import edilebilir
(birim testleri, OpenAPI üretimi). Bağlantı yalnız gerçekten gerektiğinde açılır.
"""
from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


@lru_cache
def get_engine() -> Engine:
    return create_engine(get_settings().database_url, pool_pre_ping=True)


@lru_cache
def _factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def SessionLocal() -> Session:  # noqa: N802 — eski adıyla çağrılabilsin
    return _factory()()


def __getattr__(name: str):
    """Geriye uyumluluk: `from app.db.session import engine` hâlâ çalışır (ilk erişimde oluşur)."""
    if name == "engine":
        return get_engine()
    raise AttributeError(name)


def get_db() -> Iterator[Session]:
    """FastAPI dependency: her istek kendi Session'ını alır, sonunda kapanır."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
