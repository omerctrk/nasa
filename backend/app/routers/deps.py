"""Yetki dependency'leri (sözleşme §5) — UYGULAYAN: Ömer (Ö1, app/core/security.py).

Veri giriş router'ları (A7) bu modülden import eder. Gerçek uygulama Ömer'in güvenlik
modülündedir; burası yalnız onu yeniden dışa aktarır, böylece router'lar değişmez.
Testlerde app.dependency_overrides[current_user] ile kullanıcı verilir.
"""
from app.core.security import current_user, require_active_astronaut, require_ground_control

__all__ = ["current_user", "require_active_astronaut", "require_ground_control"]
