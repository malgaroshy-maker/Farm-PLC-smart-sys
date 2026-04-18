"""Health check endpoint."""

from fastapi import APIRouter

from app.config import settings

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check():
    """Returns server health status."""
    return {
        "status": "healthy",
        "version": "0.1.0",
        "environment": settings.app_env,
        "ai_features": {
            "alarm_assistant": settings.ai_alarm_assistant_enabled,
            "smart_scheduling": settings.ai_smart_scheduling_enabled,
            "anomaly_detection": settings.ai_anomaly_detection_enabled,
            "weather_advisor": settings.ai_weather_advisor_enabled,
            "predictive_maintenance": settings.ai_predictive_maintenance_enabled,
            "water_optimizer": settings.ai_water_optimizer_enabled,
            "daily_insights": settings.ai_daily_insights_enabled,
        },
    }
