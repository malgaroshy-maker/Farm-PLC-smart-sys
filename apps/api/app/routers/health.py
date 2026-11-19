"""Health check endpoint (no auth — used by load balancers and the UI login screen)."""

from fastapi import APIRouter

from app.config import settings
from app.services.weather import weather_service

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check():
    weather_health = weather_service.health()
    return {
        "status": "healthy",
        "version": "0.3.0",
        "environment": settings.app_env,
        "deployment_mode": settings.deployment_mode,
        "ai": {
            "status": "ready",
            "primary_provider": "apinex",
            "fallback_provider": "gemini",
            "offline_fallback": settings.ai_offline_fallback,
            "timeout_sec": settings.ai_timeout_sec,
        },
        "weather": weather_health,
    }
