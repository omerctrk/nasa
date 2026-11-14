"""A4: evaluation.gercek_durum — sentetik verinin gizli gerçek etiketi ve üretim parametreleri.

YALNIZ astra_eval_role erişir. astra_app_role için şema düzeyinde açık DENY vardır (A0).
Operasyonel FK veya model girdisi değildir: bu yüzden core.Astronauts'a FK verilmez.
SANS akışı bu tabloda satır olmasını şart koşmaz.
"""
from __future__ import annotations

from sqlalchemy import CHAR, Boolean, Float, Integer, String, Unicode
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class GercekDurum(Base):
    __tablename__ = "gercek_durum"
    __table_args__ = {"schema": "evaluation"}

    astronaut_id: Mapped[str] = mapped_column(Unicode(32), primary_key=True)
    sans_label: Mapped[bool] = mapped_column(Boolean)
    onset_day: Mapped[int | None] = mapped_column(Integer)
    s_max: Mapped[float | None] = mapped_column(Float(precision=53))
    tau_days: Mapped[float | None] = mapped_column(Float(precision=53))
    eye_pattern: Mapped[str | None] = mapped_column(String(12))  # bilateral / asymmetric
    dominant_eye: Mapped[str | None] = mapped_column(CHAR(2))
    d_max: Mapped[float | None] = mapped_column(Float(precision=53))
    k: Mapped[float | None] = mapped_column(Float(precision=53))
    c: Mapped[float | None] = mapped_column(Float(precision=53))
    m: Mapped[float | None] = mapped_column(Float(precision=53))
    oct_detect_day: Mapped[int | None] = mapped_column(Integer)
