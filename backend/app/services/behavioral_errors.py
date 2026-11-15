"""Davranışsal modül iş kuralı hataları.

Servisler bu hatayı fırlatır; HTTP cevabına çevirme router katmanında (4. adım) yapılır.
"""
from __future__ import annotations

STATUS_BY_CODE = {
    "validation_error": 422,
    "future_date": 422,
    "checkin_not_found": 404,
    "not_found": 404,
    "etag_mismatch": 412,
    "precondition_required": 428,
    "weekly_not_due": 409,
    "unauthorized": 401,
}


class BehavioralError(Exception):
    def __init__(self, code: str, message: str, fields: list[str] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.status = STATUS_BY_CODE[code]      # bilinmeyen kod -> KeyError (programlama hatası)
        self.message = message
        self.fields = list(fields or [])
