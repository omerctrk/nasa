"""Repository'lerin fırlattığı ortak hatalar (gerçek ve fake uygulama aynılarını kullanır).

API katmanı bunları app/core/errors.py içinde ortak hata zarfına çevirir.
"""


class RepositoryError(Exception):
    """Tüm repository hatalarının tabanı."""


class IdempotencyConflict(RepositoryError):
    """Aynı astronot + idempotency_key farklı request_hash ile kullanıldı → 409."""


class InvalidStateTransition(RepositoryError):
    """İzin verilmeyen durum geçişi (ör. OPEN alarmı doğrudan RESOLVED, COMPLETED işi retry) → 409."""


class LeaseLost(RepositoryError):
    """lease_token artık işin sahibi değil; işçi sonucu yazmadan bırakmalı."""


class SnapshotConflict(RepositoryError):
    """İşin dondurulmuş girdisi farklı input_hash ile ezilmeye çalışıldı."""


class NotFound(RepositoryError):
    """Kayıt yok veya çağıranın erişim kapsamında değil → 404."""
