"""Versioned preparation policies. No clinical limits or sufficiency are inferred."""

from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import ConfigDict, Field, StringConstraints, model_validator

from app.schemas.common import ContractModel, Eye, MeasurementModule

# These sources must never be enabled by an accidental configuration entry.
PRIVATE_MEASUREMENTS = frozenset({"who5_score", "phq2_score", "gad2_score", "who5", "phq2", "gad2"})
DEFERRED_MEASUREMENTS = frozenset({"speed", "pvt_speed"})
Text = Annotated[str, StringConstraints(min_length=1, strip_whitespace=True, strict=True)]


class PolicyModel(ContractModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class MeasurementContext(PolicyModel):
    module: MeasurementModule
    measurement: Text
    unit: Text
    protocol_version: Text
    eye: Eye | None = None

    def key(self) -> tuple:
        return (self.module.value, self.measurement, self.unit, self.protocol_version,
                self.eye.value if self.eye else "")

    @model_validator(mode="after")
    def allowed_context(self) -> Self:
        if self.measurement.lower() in PRIVATE_MEASUREMENTS | DEFERRED_MEASUREMENTS:
            raise ValueError("Ölçüm model kapsamı dışında.")
        if self.module != MeasurementModule.SANS and self.eye is not None:
            raise ValueError("Göz dışı ölçümde eye null olmalıdır.")
        return self


class ThresholdRule(MeasurementContext):
    lower: Decimal | None = None
    upper: Decimal | None = None

    @model_validator(mode="after")
    def valid_bounds(self) -> Self:
        if self.lower is None and self.upper is None:
            raise ValueError("En az bir eşik sınırı zorunlu.")
        if self.lower is not None and self.upper is not None and self.lower > self.upper:
            raise ValueError("Alt sınır üst sınırı aşamaz.")
        return self


class ThresholdPolicy(PolicyModel):
    version: Text
    boundary: Literal["inclusive"] = "inclusive"
    # Sınırların nereden geldiği (ör. "demo, klinik değil"); snapshot'a politika ile birlikte donar.
    source_note: Text | None = None
    rules: tuple[ThresholdRule, ...] = ()

    @model_validator(mode="after")
    def unique_contexts(self) -> Self:
        keys = [rule.key() for rule in self.rules]
        if len(keys) != len(set(keys)):
            raise ValueError("Aynı ölçüm bağlamına iki eşik tanımlanamaz.")
        return self


class FeatureDefinition(PolicyModel):
    module: MeasurementModule
    measurement: Text
    unit: Text
    protocol_version: Text
    definition_confirmed: Annotated[bool, Field(strict=True)] = False
    minimum_quality_score: Decimal | None = Field(default=None, ge=0, le=1)

    @model_validator(mode="after")
    def allowed_feature(self) -> Self:
        if self.measurement.lower() in PRIVATE_MEASUREMENTS | DEFERRED_MEASUREMENTS:
            raise ValueError("Ölçüm model kapsamı dışında.")
        return self

    def key(self) -> tuple:
        return (self.module.value, self.measurement, self.unit, self.protocol_version)


class HistoryPolicy(PolicyModel):
    version: Text
    summary_days: Literal[74] = 74
    recent_days: Literal[7] = 7
    sufficiency_policy_status: Literal["not_configured"] = "not_configured"
    features: tuple[FeatureDefinition, ...]

    @model_validator(mode="after")
    def unique_features(self) -> Self:
        keys = [feature.key() for feature in self.features]
        if len(keys) != len(set(keys)):
            raise ValueError("Aynı özellik bağlamı iki kez tanımlanamaz.")
        return self
