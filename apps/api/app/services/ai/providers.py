"""AI Provider Management and Dynamic Model Fetching (Milestone E).

Primary: APInex (OpenAI-compatible) OpenAIChatModel with OpenAIProvider
Fallback: GoogleModel with GoogleProvider
Dynamic model fetching from APInex GET /v1/models with TTL caching.
"""

import logging
from datetime import datetime
from typing import Any

import httpx
from pydantic_ai.models import Model
from pydantic_ai.models.fallback import FallbackModel
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.google import GoogleProvider
from pydantic_ai.providers.openai import OpenAIProvider

from app.config import settings
from app.core.timeutil import utcnow

log = logging.getLogger(__name__)

# Cached APInex models list
_APINEX_MODELS_CACHE: list[str] = []
_APINEX_MODELS_CACHE_TIME: datetime | None = None
APINEX_CACHE_TTL_SEC = 3600  # 1 hour


async def fetch_apinex_models(
    base_url: str | None = None,
    api_key: str | None = None,
    force_refresh: bool = False,
) -> list[str]:
    """Fetch available models from APInex GET /v1/models with 1-hour cache."""
    global _APINEX_MODELS_CACHE, _APINEX_MODELS_CACHE_TIME

    url = (base_url or settings.apinex_base_url).rstrip("/")
    key = api_key if api_key is not None else settings.apinex_api_key

    now = utcnow()
    if (
        not force_refresh
        and _APINEX_MODELS_CACHE
        and _APINEX_MODELS_CACHE_TIME is not None
        and (now - _APINEX_MODELS_CACHE_TIME).total_seconds() < APINEX_CACHE_TTL_SEC
    ):
        return list(_APINEX_MODELS_CACHE)

    models_endpoint = f"{url}/models"
    headers = {"Authorization": f"Bearer {key}"} if key else {}

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(models_endpoint, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("data", [])
                models = [item["id"] for item in items if isinstance(item, dict) and "id" in item]
                if models:
                    _APINEX_MODELS_CACHE = models
                    _APINEX_MODELS_CACHE_TIME = now
                    log.info("Fetched %d models from APInex: %s", len(models), models[:5])
                    return list(_APINEX_MODELS_CACHE)
    except Exception as exc:
        log.warning("Could not fetch models dynamically from APInex (%s): %s", models_endpoint, exc)

    # Fallback to configured model or standard default
    default = settings.apinex_model or "gpt-4o-mini"
    return [default]


def get_primary_model(model_name: str | None = None) -> OpenAIChatModel:
    """Build APInex OpenAI-compatible Chat Model."""
    name = model_name or settings.apinex_model or "gpt-4o-mini"
    provider = OpenAIProvider(
        base_url=settings.apinex_base_url,
        api_key=settings.apinex_api_key or "no-key",
    )
    return OpenAIChatModel(name, provider=provider)


def get_fallback_model(model_name: str | None = None) -> GoogleModel:
    """Build Google Gemini Fallback Model."""
    name = model_name or settings.gemini_model or "gemini-2.5-flash"
    provider = GoogleProvider(
        api_key=settings.gemini_api_key or "no-key",
    )
    return GoogleModel(name, provider=provider)


def build_fallback_chain(
    primary_model: Model | None = None,
    fallback_model: Model | None = None,
) -> FallbackModel:
    """Construct Pydantic AI FallbackModel chain (APInex -> Gemini)."""
    p_model = primary_model or get_primary_model()
    f_model = fallback_model or get_fallback_model()

    return FallbackModel(p_model, f_model, fallback_on=(Exception,))


def identify_provider_label(response_obj: Any) -> str:
    """Classify which provider in the chain serviced the request."""
    if response_obj is None:
        return "rule_based"

    # Inspect provider_name and model_name
    p_name = str(getattr(response_obj, "provider_name", "")).lower()
    m_name = str(getattr(response_obj, "model_name", "")).lower()

    if "google" in p_name or "gemini" in m_name:
        return "gemini"
    elif "openai" in p_name or "apinex" in p_name or "gpt" in m_name:
        return "apinex"
    elif "test" in p_name or "test" in m_name or "function" in p_name:
        return "test"
    return "apinex"
