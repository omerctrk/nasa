"""Eşik politikası okuma ucu: GET /api/v1/thresholds (giriş yapmış her kullanıcı).

Frontend bir ölçümün "aralık dışı" olduğunu analizle AYNI kaynaktan (config/thresholds.json,
Ömer'in ThresholdPolicy'si) okur; sınır iki yerde ayrı yazılmaz. Sınırlar ondalık METİN
olarak döner (yuvarlama yok). Politika klinik değil demodur: source_note bunu taşır.
"""
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from pydantic import Field

from app.core.config import get_settings
from app.routers.deps import current_user
from app.schemas.common import ContractModel, CurrentUser
from app.services.thresholds import load_threshold_policy

router = APIRouter(tags=["eşikler"])


class ThresholdRuleOut(ContractModel):
    module: str
    measurement: str
    unit: str
    protocol_version: str
    lower: str | None = None
    upper: str | None = None


class ThresholdPolicyOut(ContractModel):
    version: str
    boundary: str = Field(description="inclusive: sınıra eşit değer aralık içidir")
    source_note: str | None
    rules: list[ThresholdRuleOut]


@router.get("/thresholds", response_model=ThresholdPolicyOut)
def get_thresholds(response: Response,
                   user: Annotated[CurrentUser, Depends(current_user)]) -> ThresholdPolicyOut:
    policy = load_threshold_policy(get_settings().threshold_policy_path)
    response.headers["Cache-Control"] = "no-store"
    return ThresholdPolicyOut(
        version=policy.version, boundary=policy.boundary, source_note=policy.source_note,
        rules=[ThresholdRuleOut(module=r.module.value, measurement=r.measurement, unit=r.unit,
                                protocol_version=r.protocol_version,
                                lower=str(r.lower) if r.lower is not None else None,
                                upper=str(r.upper) if r.upper is not None else None)
               for r in policy.rules])
