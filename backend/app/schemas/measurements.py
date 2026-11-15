"""Fizyolojik ölçüm girişi DTO'ları (A7, sahip: Aybala).

Yalnız sözlükte module=physiological olan kodlar kabul edilir; birim sözlükteki kanonik
birimle aynı olmalıdır (dönüşüm yapılmaz). Sensör bağlantısı kapsam dışı: manuel giriş.
"""
from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from pydantic import Field, field_validator, model_validator

from app.schemas.behavioral import utc
from app.schemas.common import ContractModel, JsonDecimal


class PhysiologicalIn(ContractModel):
    client_request_id: uuid.UUID
    measurement: str = Field(min_length=1, max_length=60)
    value_num: JsonDecimal | None = None
    value_text: str | None = Field(default=None, max_length=256)
    unit: str = Field(min_length=1, max_length=32)
    measured_date: dt.date
    measured_at: dt.datetime | None = None  # yalnız gerçek saat biliniyorsa
    quality_score: JsonDecimal | None = Field(default=None, ge=0, le=1)
    valid: bool = True
    metadata_json: dict[str, Any] | None = None

    @field_validator("measured_at")
    @classmethod
    def _utc(cls, v: dt.datetime | None) -> dt.datetime | None:
        return utc(v) if v is not None else None

    @model_validator(mode="after")
    def _rules(self) -> PhysiologicalIn:
        if self.value_num is not None and self.value_text is not None:
            raise ValueError("value_num ve value_text aynı anda dolu olamaz")
        if self.valid and self.value_num is None and self.value_text is None:
            raise ValueError("geçerli ölçümde değer zorunlu (eksik değer 0 yapılmaz)")
        if self.measured_at is not None and self.measured_at.date() != self.measured_date:
            raise ValueError("measured_date, measured_at'in UTC tarihi olmalı")
        return self


class PhysiologicalOut(ContractModel):
    record_id: uuid.UUID
    measurement: str
    measured_date: dt.date
    mission_day: int
    created: bool
