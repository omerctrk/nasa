"""SQLAlchemy declarative base for durable ASTRA HEALTH records."""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class used by all SQLAlchemy persistence models."""
