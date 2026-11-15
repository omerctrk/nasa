"""Listeleme uçlarının ortak kuralları: limit, tarih aralığı, opak cursor.

Cursor, son kaydın sıralama anahtarının base64 metnidir; istemci için anlamsızdır.
"""
from __future__ import annotations

import base64
import binascii
from datetime import date, datetime

from app.services.behavioral_errors import BehavioralError

DEFAULT_LIMIT = 30
MAX_LIMIT = 100


def check_limit(limit: int) -> None:
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_LIMIT:
        raise BehavioralError("validation_error", f"limit must be between 1 and {MAX_LIMIT}", ["limit"])


def check_range(date_from: date | None, date_to: date | None) -> None:
    if date_from is not None and date_to is not None and date_from > date_to:
        raise BehavioralError("validation_error", "from must not be later than to", ["from", "to"])


def _bad_cursor() -> BehavioralError:
    return BehavioralError("validation_error", "Invalid cursor", ["cursor"])


def encode_text(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode("ascii")).decode("ascii")


def decode_text(cursor: str) -> str:
    try:
        return base64.urlsafe_b64decode(cursor.encode("ascii")).decode("ascii")
    except (ValueError, binascii.Error, UnicodeError):
        raise _bad_cursor() from None


def encode_date(d: date) -> str:
    return encode_text(d.isoformat())


def decode_date(cursor: str) -> date:
    try:
        return date.fromisoformat(decode_text(cursor))
    except ValueError:
        raise _bad_cursor() from None


def encode_position(moment: datetime, id: int) -> str:
    """(zaman, id) sıralama anahtarı -> cursor."""
    return encode_text(f"{moment.isoformat()}|{id}")


def decode_position(cursor: str) -> tuple[datetime, int]:
    try:
        moment_text, id_text = decode_text(cursor).split("|")
        moment, id = datetime.fromisoformat(moment_text), int(id_text)
    except ValueError:
        raise _bad_cursor() from None
    if moment.tzinfo is None:
        raise _bad_cursor()
    return moment, id
