"""AI Provider Management and Dynamic Model Fetching (Milestone E).

Primary: APInex (OpenAI-compatible) OpenAIChatModel with OpenAIProvider
Fallback: GoogleModel with GoogleProvider
Dynamic model fetching from APInex GET /v1/models with TTL caching.
"""

import logging
from datetime import datetime
from typing import Any
from urllib.parse import urlsplit

import httpx
from pydantic_ai.models import Model
from pydantic_ai.models.fallback import FallbackModel
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.google import GoogleProvider
from pydantic_ai.providers.openai import OpenAIProvider

from app.config import settings
from app.core.timeutil import utcnow
from app.services.ai.model_catalog import is_model_available

log = logging.getLogger(__name__)

# Cached APInex models list
_APINEX_MODELS_CACHE: list[str] = []
_APINEX_MODELS_CACHE_TIME: datetime | None = None
APINEX_CACHE_TTL_SEC = 3600  # 1 hour


def validated_apinex_url(value: str | None = None) -> str:
    """Keep provider credentials on the deployment-configured HTTPS endpoint."""
    approved = settings.apinex_base_url.rstrip("/")
    requested = (value or approved).rstrip("/")
    parts = urlsplit(requested)
    if (
        requested != approved
        or parts.scheme != "https"
        or not parts.hostname
        or any((parts.username, parts.password, parts.query, parts.fragment))
    ):
        raise ValueError("APInex endpoint must match the configured HTTPS provider URL")
    return requested


async def fetch_apinex_models(
    base_url: str | None = None,
    api_key: str | None = None,
    force_refresh: bool = False,
) -> list[str]:
    """Fetch available models from APInex GET /v1/models with 1-hour cache."""
    global _APINEX_MODELS_CACHE, _APINEX_MODELS_CACHE_TIME

    url = validated_apinex_url(base_url)
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
        log.warning("Could not fetch APInex models (%s)", type(exc).__name__)

    # Fallback to configured model or standard default
    default = settings.apinex_model or "free/deepseek-v4-pro-0813"
    return [default]


def get_primary_model(
    model_name: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
) -> OpenAIChatModel:
    """Build APInex OpenAI-compatible Chat Model."""
    name = model_name or settings.apinex_model or "free/deepseek-v4-pro-0813"
    provider = OpenAIProvider(
        base_url=validated_apinex_url(base_url),
        api_key=api_key or settings.apinex_api_key or "no-key",
    )
    return OpenAIChatModel(name, provider=provider)


def get_apinex_fallback_model(
    model_name: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
) -> OpenAIChatModel:
    """Build secondary APInex fallback model (e.g. free/minimax-m3.1-flash)."""
    name = model_name or settings.apinex_fallback_model or "free/minimax-m3.1-flash"
    provider = OpenAIProvider(
        base_url=validated_apinex_url(base_url),
        api_key=api_key or settings.apinex_api_key or "no-key",
    )
    return OpenAIChatModel(name, provider=provider)


def get_fallback_model(
    model_name: str | None = None,
    api_key: str | None = None,
) -> GoogleModel:
    """Build Google Gemini Fallback Model."""
    name = model_name or settings.gemini_model or "gemini-2.5-flash"
    provider = GoogleProvider(
        api_key=api_key or settings.gemini_api_key or "no-key",
    )
    return GoogleModel(name, provider=provider)


def build_fallback_chain(
    primary_model: Model | None = None,
    secondary_model: Model | None = None,
    fallback_model: Model | None = None,
) -> FallbackModel:
    """Construct Pydantic AI FallbackModel chain (APInex -> APInex Fallback -> Gemini).

    Excludes any models marked runtime unavailable (e.g. HTTP 400/402).
    """
    p_model = primary_model or get_primary_model()
    s_model = secondary_model or get_apinex_fallback_model()
    f_model = fallback_model or get_fallback_model()

    active_models: list[Model] = []
    for m in (p_model, s_model):
        m_name = getattr(m, "model_name", None) or getattr(m, "_model_name", None)
        if m_name and not is_model_available(str(m_name)):
            log.info("Excluding unavailable model '%s' from fallback chain", m_name)
            continue
        active_models.append(m)

    active_models.append(f_model)

    if len(active_models) == 1:
        return FallbackModel(active_models[0], f_model, fallback_on=(Exception,))

    return FallbackModel(active_models[0], *active_models[1:], fallback_on=(Exception,))


def configured_chain(
    primary: str = "apinex",
    fallback: str = "gemini",
    *,
    apinex_model: str | None = None,
    apinex_secondary: str | None = None,
    gemini_model: str | None = None,
    base_url: str | None = None,
) -> Model | None:
    """Build the saved provider order using configured credentials and model availability."""
    candidates: list[Model] = []
    for provider in dict.fromkeys((primary, fallback)):
        if provider == "apinex" and settings.apinex_api_key:
            ids = (
                apinex_model or settings.apinex_model,
                apinex_secondary or settings.apinex_fallback_model,
            )
            candidates.extend(
                get_primary_model(model_name=model, base_url=base_url)
                for model in dict.fromkeys(ids)
                if is_model_available(model)
            )
        elif provider == "gemini" and settings.gemini_api_key:
            candidates.append(get_fallback_model(model_name=gemini_model))
    if len(candidates) < 2:
        return candidates[0] if candidates else None
    return FallbackModel(candidates[0], *candidates[1:])


def identify_provider_label(response_obj: Any) -> str:
    """Classify which provider in the chain serviced the request."""
    if response_obj is None:
        return "rule_based"

    # Inspect provider_name and model_name
    p_name = str(getattr(response_obj, "provider_name", "")).lower()
    m_name = str(getattr(response_obj, "model_name", "")).lower()

    if (
        "test" in p_name
        or "test" in m_name
        or "function" in p_name
        or m_name.startswith("function:")
    ):
        return "test"
    if "openai" in p_name or "apinex" in p_name:
        return "apinex"
    if "google" in p_name:
        return "gemini"
    if "gemini" in m_name and "openai" not in p_name:
        return "gemini"
    return "apinex"
