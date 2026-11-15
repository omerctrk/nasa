"""Health-check route."""

from fastapi import APIRouter

from app.core.config import get_settings
from app.schemas.knowledge_card import HealthResponse


router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    """Report only API process health; no external dependency is checked here."""
    settings = get_settings()
    return HealthResponse(
        status="healthy",
        application=settings.app_name,
        version=settings.app_version,
    )
