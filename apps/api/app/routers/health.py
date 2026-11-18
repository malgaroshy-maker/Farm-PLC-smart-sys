"""Health check endpoint (no auth — used by load balancers and the UI login screen)."""

from fastapi import APIRouter

from app.config import settings

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "version": "0.2.0",
        "environment": settings.app_env,
        "deployment_mode": settings.deployment_mode,
        # Reported honestly: AI features are specified but not built yet (Milestone E).
        "ai": "not_implemented",
    }
