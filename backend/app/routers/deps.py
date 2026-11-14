"""Yetki dependency'leri (sözleşme §5) — UYGULAYAN: Ömer (Ö1).

Bu dosya şimdilik YER TUTUCUDUR: imzalar sözleşmedeki gibidir, Aybala'nın veri giriş
router'ları bunlara bağlıdır. Ömer JWT doğrulamasını ve DB'den güncel rol/aktiflik/
gösterim kontrolünü yazınca yalnız current_user() gövdesi değişir; router'lar değişmez.

Testlerde app.dependency_overrides[current_user] ile gerçek kullanıcı verilir.
"""
from fastapi import Depends

from app.core.errors import ApiError
from app.schemas.common import CurrentUser, ErrorCode, Role


def current_user() -> CurrentUser:
    """Token + aktif hesap doğrulaması. YER TUTUCU: Ö1 gelene kadar her isteği reddeder."""
    raise ApiError(401, ErrorCode.UNAUTHORIZED, "Giriş henüz etkin değil (Ö1 bekleniyor).")


def require_active_astronaut(user: CurrentUser = Depends(current_user)) -> CurrentUser:
    """ASTRONAUT rolü + kendi astronot bağlantısı. Gösterim profili kontrolünü Ö1 DB'den
    yapar; veri giriş servisi ayrıca kendisi de kontrol eder (çift güvenlik)."""
    if user.role is not Role.ASTRONAUT or user.astronaut_id is None:
        raise ApiError(403, ErrorCode.FORBIDDEN)
    return user


def require_ground_control(user: CurrentUser = Depends(current_user)) -> CurrentUser:
    if user.role is not Role.GROUND_CONTROL:
        raise ApiError(403, ErrorCode.FORBIDDEN)
    return user
