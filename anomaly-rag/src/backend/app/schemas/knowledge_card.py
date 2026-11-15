"""Validation schemas for source-traceable RAG knowledge cards."""

from __future__ import annotations

from typing import Annotated, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


CardType = Literal["risk", "sign", "countermeasure", "emergency"]
Direction = Literal["up", "down", "any"]

ALLOWED_METRICS: Final[frozenset[str]] = frozenset(
    {
        "mood_index",
        "stress",
        "loneliness",
        "crew_relation",
        "sleep_hours",
        "sleep_quality",
        "pvt_mean_rt_ms",
        "pvt_lapses",
        "pvt_false_starts",
        "rotation_accuracy",
        "rotation_mean_rt_ms",
        "heart_rate",
        "systolic_bp",
        "diastolic_bp",
        "spo2",
        "respiratory_rate",
        "body_temp",
        "visual_acuity",
        "headache",
        "fatigue",
        "nausea",
        "dizziness",
        "blurred_vision",
        "eye_pressure",
        "back_pain",
        "cough",
        "shortness_of_breath",
        "sore_throat",
        "skin_lesion",
        "digestive_issue",
    }
)

# This is a registry, not a Python Enum. New systems require an explicit
# reviewed registry addition; unknown source values are never remapped.
SYSTEM_CATALOG: Final[dict[str, str]] = {
    "behavioral": "Behavioral self-report measures",
    "cognitive": "Cognitive and reflex tests",
    "cardiovascular": "Heart rate and blood-pressure measures",
    "respiratory": "Respiratory measures and symptoms",
    "thermal": "Body-temperature measures",
    "renal": "Renal laboratory measures",
    "vision": "Vision and eye-related measures",
    "sensorimotor": "Sensorimotor measures",
    "symptoms": "Reported symptoms",
}

CardId = Annotated[
    str,
    Field(
        min_length=3,
        max_length=80,
        pattern=r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$",
        description="Lowercase, hyphen-separated knowledge card identifier.",
    ),
]


class KnowledgeCard(BaseModel):
    """A concise, source-linked scientific information card for retrieval."""

    id: CardId
    type: CardType
    system: Annotated[str, Field(min_length=1, max_length=64)]
    metrics: list[str] = Field(default_factory=list)
    direction: Direction
    text: Annotated[str, Field(min_length=1, max_length=2_000)]
    source: Annotated[str, Field(min_length=1, max_length=500)]
    url: HttpUrl
    locator: Annotated[str, Field(min_length=1, max_length=500)]

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @field_validator("system")
    @classmethod
    def validate_system(cls, value: str) -> str:
        if value not in SYSTEM_CATALOG:
            allowed = ", ".join(sorted(SYSTEM_CATALOG))
            raise ValueError(
                f"Unsupported system '{value}'. Add it to the reviewed system catalog first. "
                f"Accepted systems: {allowed}."
            )
        return value

    @field_validator("metrics")
    @classmethod
    def validate_metrics(cls, metrics: list[str]) -> list[str]:
        unknown_metrics = sorted(set(metrics).difference(ALLOWED_METRICS))
        if unknown_metrics:
            raise ValueError(f"Unsupported metrics: {', '.join(unknown_metrics)}")
        return metrics

    @field_validator("text")
    @classmethod
    def validate_text_word_count(cls, value: str) -> str:
        if not value:
            raise ValueError("text must not be empty")
        if len(value.split()) > 60:
            raise ValueError("text must contain at most 60 words")
        return value


class HealthResponse(BaseModel):
    """Response returned by the API health endpoint."""

    status: Literal["healthy"]
    application: str
    version: str
