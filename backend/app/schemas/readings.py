"""Okuma uçlarının yanıt modelleri (Aybala).

Genetik/SANS başlangıç alanları (mtrr66_g, b_vit_status …) ekrana verilmez: model girdisidir,
panelde gösterilmesi gerekmez ve hassastır.
"""
from __future__ import annotations

import datetime as dt
from app.schemas.common import ContractModel


class ProfileOut(ContractModel):
    astronaut_id: str
    display_name: str
    is_display_only: bool
    mission_id: str
    mission_name: str
    mission_start_date: dt.date  # görev günü 0
    mission_length_days: int
    scenario: str | None


class CognitiveDetailOut(ContractModel):
    id: int
    taken_at: dt.datetime
    mission_day: int
    test_type: str
    duration_s: int
    n_trials: int
    mean_rt_ms: float | None
    median_rt_ms: float | None
    lapses: int | None
    false_starts: int | None
    accuracy: float | None
    correct_count: int | None
    valid: bool
    invalid_reason: str | None
    device: str
