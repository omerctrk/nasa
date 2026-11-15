"""Bellek içi repository'ler (testler ve veritabanı hazır olana kadar).

Kayıtların kopyası saklanır ve döndürülür; astronotlar birbirinin kaydını göremez.
"""
from __future__ import annotations

import copy
from dataclasses import replace
from datetime import date, datetime
from uuid import UUID

from app.repositories.behavioral import CheckinRecord, CognitiveTestRecord, WeeklyRecord


def _copy(record):
    """Dışarıdaki nesne değişse de saklanan kayıt etkilenmesin."""
    return copy.deepcopy(record)


def _in_range(d: date, date_from: date | None, date_to: date | None) -> bool:
    return (date_from is None or d >= date_from) and (date_to is None or d <= date_to)


class InMemoryCheckinRepository:
    def __init__(self) -> None:
        self._rows: dict[tuple[str, date], CheckinRecord] = {}
        self._next_id = 1

    def get_by_date(self, astronaut_id: str, date: date) -> CheckinRecord | None:
        row = self._rows.get((astronaut_id, date))
        return _copy(row) if row else None

    def list(self, astronaut_id: str, date_from: date | None, date_to: date | None,
             limit: int, after_date: date | None) -> list[CheckinRecord]:
        rows = [
            r for (owner, d), r in self._rows.items()
            if owner == astronaut_id and _in_range(d, date_from, date_to)
            and (after_date is None or d < after_date)
        ]
        rows.sort(key=lambda r: r.date, reverse=True)
        return [_copy(r) for r in rows[:limit]]

    def add(self, record: CheckinRecord) -> CheckinRecord:
        stored = replace(_copy(record), id=self._next_id)
        self._next_id += 1
        self._rows[(stored.astronaut_id, stored.date)] = stored
        return _copy(stored)

    def update(self, record: CheckinRecord) -> CheckinRecord:
        key = (record.astronaut_id, record.date)
        if key not in self._rows:
            raise KeyError(key)
        self._rows[key] = _copy(record)
        return _copy(record)


class _ByIdStore:
    """id ile saklayan ortak taban (bilişsel testler ve haftalık ölçekler)."""

    def __init__(self) -> None:
        self._rows: dict[int, object] = {}
        self._next_id = 1

    def _owned(self, astronaut_id: str) -> list:
        return [r for r in self._rows.values() if r.astronaut_id == astronaut_id]

    def get_by_id(self, astronaut_id: str, id: int):
        row = self._rows.get(id)
        return _copy(row) if row is not None and row.astronaut_id == astronaut_id else None

    def get_by_client_request_id(self, astronaut_id: str, client_request_id: UUID):
        for r in self._owned(astronaut_id):
            if r.client_request_id == client_request_id:
                return _copy(r)
        return None

    def add(self, record):
        stored = replace(_copy(record), id=self._next_id)
        self._next_id += 1
        self._rows[stored.id] = stored
        return _copy(stored)


class InMemoryCognitiveTestRepository(_ByIdStore):
    def list(self, astronaut_id: str, date_from: date | None, date_to: date | None,
             test_type: str | None, limit: int,
             after: tuple[datetime, int] | None) -> list[CognitiveTestRecord]:
        rows = [
            r for r in self._owned(astronaut_id)
            if _in_range(r.date, date_from, date_to)
            and (test_type is None or r.test_type == test_type)
            and (after is None or (r.started_at, r.id) < after)
        ]
        rows.sort(key=lambda r: (r.started_at, r.id), reverse=True)
        return [_copy(r) for r in rows[:limit]]


class InMemoryWeeklyRepository(_ByIdStore):
    def get_latest(self, astronaut_id: str) -> WeeklyRecord | None:
        rows = self._owned(astronaut_id)
        if not rows:
            return None
        return _copy(max(rows, key=lambda r: (r.date, r.created_at, r.id)))

    def list(self, astronaut_id: str, date_from: date | None, date_to: date | None,
             limit: int, after: tuple[datetime, int] | None) -> list[WeeklyRecord]:
        rows = [
            r for r in self._owned(astronaut_id)
            if _in_range(r.date, date_from, date_to)
            and (after is None or (r.created_at, r.id) < after)
        ]
        rows.sort(key=lambda r: (r.created_at, r.id), reverse=True)
        return [_copy(r) for r in rows[:limit]]

    def update(self, record: WeeklyRecord) -> WeeklyRecord:
        current = self._rows.get(record.id)
        if current is None or current.astronaut_id != record.astronaut_id:
            raise KeyError(record.id)
        self._rows[record.id] = _copy(record)
        return _copy(record)
