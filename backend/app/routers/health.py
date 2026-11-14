"""live / ready kontrolleri (sahip: Aybala, şema §11)."""
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db

router = APIRouter(tags=["health"])


@router.get("/health/live")
def live() -> dict:
    """Süreç ayakta mı? Veritabanına dokunmaz."""
    return {"status": "ok"}


@router.get("/health/ready")
def ready(db: Session = Depends(get_db)) -> dict:
    """Veritabanına sınırlı hesapla bağlanılabiliyor mu? db_user 'astra_app' olmalı, 'sa' değil."""
    user = db.execute(text("SELECT USER_NAME()")).scalar_one()
    return {"status": "ok", "database": "ok", "db_user": user}
