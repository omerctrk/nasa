"""Ham göz verisi ve baş ağrısı DTO'ları (A7, sahip: Aybala).

Bir göz oturumu = 3 test (near_acuity, contrast, amsler) × 2 göz (OD, OS) = 6 sonuç.
Tekrar test önceki oturuma retest_of ile bağlanır. Değerler ham kaydedilir; yorum SANS'ın.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal

from pydantic import Field, model_validator

from app.schemas.common import ContractModel, Eye, JsonDecimal

UNITS = {"near_acuity": "logMAR", "contrast": "logCS", "amsler": "cells"}


class EyeTestIn(ContractModel):
    eye: Eye
    test: Literal["near_acuity", "contrast", "amsler"]
    value: Decimal  # logMAR negatif olabilir; genel >=0 kuralı yok
    unit: Literal["logMAR", "logCS", "cells"]
    amsler_cells: list[list[float]] | None = None
    n_correct: int | None = Field(default=None, ge=0)
    n_presented: int | None = Field(default=None, ge=0)
    duration_s: Decimal | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _rules(self) -> EyeTestIn:
        if UNITS[self.test] != self.unit:
            raise ValueError(f"{self.test} birimi {UNITS[self.test]} olmalı")
        if self.amsler_cells is not None and self.test != "amsler":
            raise ValueError("amsler_cells yalnız amsler testinde")
        if (self.n_correct is None) != (self.n_presented is None):
            raise ValueError("n_correct ve n_presented birlikte verilir")
        if self.n_correct is not None and self.n_correct > self.n_presented:
            raise ValueError("n_correct, n_presented'dan büyük olamaz")
        return self


class EyeSessionIn(ContractModel):
    """POST /me/eye-sessions. session_id backend üretir: S-<astronot>-D<gün> / M<gün>."""

    flight_day: int  # uçuş öncesi negatif olabilir
    retest_of: str | None = None
    quality_score: Decimal = Field(ge=0, le=1)
    checklist: dict[str, Any] | None = None  # mesafe/ışık/gözlük… kalite kontrolü
    tests: list[EyeTestIn]

    @model_validator(mode="after")
    def _full_session(self) -> EyeSessionIn:
        combos = {(t.eye, t.test) for t in self.tests}
        if len(self.tests) != 6 or len(combos) != 6:
            raise ValueError("tam oturum: 3 test × OD/OS = 6 farklı sonuç")
        return self


class EyeSessionOut(ContractModel):
    session_id: str
    flight_day: int
    is_retest: bool
    retest_of: str | None
    quality_score: JsonDecimal
    test_count: int


class HeadacheIn(ContractModel):
    """POST /me/symptoms/headache — baş ağrısının TEK kaynağı (sans.semptom)."""

    flight_day: int
    headache: bool


class HeadacheOut(ContractModel):
    flight_day: int
    headache: bool
