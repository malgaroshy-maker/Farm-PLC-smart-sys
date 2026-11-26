"""AI Model Catalog and Runtime Availability Tracker (Milestone E Round 3).

Contains catalog data for all 23 APInex free models from docs/AI_MODELS.md
with quota multipliers (×2/×3/×5), tool support, vision support, and verdict badges.
Tracks runtime 400/402 unavailable models in an in-memory cache so they are
marked unavailable and excluded from fallback chains.
"""

from pydantic import BaseModel, Field


class ModelCatalogEntry(BaseModel):
    """Metadata for an AI model in the farm's catalog."""

    model_id: str
    quota_multiplier: int = Field(
        default=1, description="Quota multiplier (e.g. 2 for ×2, 3 for ×3)"
    )
    supports_tools: bool = Field(
        default=True, description="Whether the model reliably supports function/tool calling"
    )
    supports_vision: bool = Field(
        default=False, description="Whether the model accepts vision/image inputs"
    )
    verdict: str = Field(
        default="mixing", description="'recommended' | 'mixing' | 'avoid' | 'unavailable'"
    )
    verdict_badge: str = Field(default="⚠", description="'✓' | '⚠' | '⛔'")
    description: str = Field(default="", description="Benchmark summary and guidance")
    available: bool = Field(
        default=True, description="Whether the model is currently usable with the key"
    )
    unavailable_reason: str | None = Field(
        default=None, description="Reason if marked unavailable (e.g. HTTP 402)"
    )


# All 23 free models from docs/AI_MODELS.md benchmark:
STATIC_MODEL_CATALOG: list[ModelCatalogEntry] = [
    # ── Recommended ─────────────────────────────────────────────────────────────
    ModelCatalogEntry(
        model_id="free/deepseek-v4-pro-0813",
        quota_multiplier=3,
        supports_tools=True,
        supports_vision=False,
        verdict="recommended",
        verdict_badge="✓",
        description="Recommended default: fastest working model (4.5 s answer from the live snapshot, 2026-11-23)",
        available=True,
    ),
    ModelCatalogEntry(
        model_id="free/muse-spark-1.3",
        quota_multiplier=3,
        supports_tools=True,
        supports_vision=True,
        verdict="unavailable",
        verdict_badge="⛔",
        description="Recommended second: cleanest Arabic, slow or variable latency",
        available=False,
        unavailable_reason="HTTP 402: subscription only (re-tested 2026-11-23)",
    ),
    # ── Working with Noticeable Mixing ──────────────────────────────────────────
    ModelCatalogEntry(
        model_id="free/gemini-3.8-flash",
        quota_multiplier=3,
        supports_tools=True,
        supports_vision=True,
        verdict="unavailable",
        verdict_badge="⛔",
        description="Fast; mixes in Korean and English words",
        available=False,
        unavailable_reason="HTTP 402: subscription only (re-tested 2026-11-23)",
    ),
    ModelCatalogEntry(
        model_id="free/hy4",
        quota_multiplier=2,
        supports_tools=True,
        supports_vision=True,
        verdict="unavailable",
        verdict_badge="⛔",
        description="Cheaper (×2); slow latency",
        available=False,
        unavailable_reason="HTTP 402: subscription only (re-tested 2026-11-23)",
    ),
    ModelCatalogEntry(
        model_id="free/hy4-flash",
        quota_multiplier=2,
        supports_tools=True,
        supports_vision=True,
        verdict="unavailable",
        verdict_badge="⛔",
        description="Cheap and fast (×2); noticeable mixing",
        available=False,
        unavailable_reason="HTTP 402: subscription only (re-tested 2026-11-23)",
    ),
    ModelCatalogEntry(
        model_id="free/deepseek-v4.1-flash",
        quota_multiplier=3,
        supports_tools=True,
        supports_vision=True,
        verdict="mixing",
        verdict_badge="⚠",
        description="Fast; mixing",
        available=True,
    ),
    ModelCatalogEntry(
        model_id="free/qwen-3.8-max",
        quota_multiplier=3,
        supports_tools=True,
        supports_vision=True,
        verdict="mixing",
        verdict_badge="⚠",
        description="English words in Arabic",
        available=True,
    ),
    ModelCatalogEntry(
        model_id="free/glm-5.3-flash",
        quota_multiplier=3,
        supports_tools=True,
        supports_vision=True,
        verdict="mixing",
        verdict_badge="⚠",
        description="Mixing; large prompts (2.3k input tokens)",
        available=True,
    ),
    ModelCatalogEntry(
        model_id="free/glm-5.3-flashx",
        quota_multiplier=3,
        supports_tools=True,
        supports_vision=True,
        verdict="mixing",
        verdict_badge="⚠",
        description="Mixing",
        available=True,
    ),
    ModelCatalogEntry(
        model_id="free/minimax-m3.1-flash",
        quota_multiplier=2,
        supports_tools=True,
        supports_vision=True,
        verdict="recommended",
        verdict_badge="✓",
        description="Recommended backup (2026-11-23 test): the only model with clean Arabic on both the chat and alarm tasks",
        available=True,
    ),
    ModelCatalogEntry(
        model_id="free/mimo-v2.6-pro",
        quota_multiplier=2,
        supports_tools=True,
        supports_vision=True,
        verdict="unavailable",
        verdict_badge="⛔",
        description="Slow and mixing",
        available=False,
        unavailable_reason="HTTP 402: subscription only (re-tested 2026-11-23)",
    ),
    ModelCatalogEntry(
        model_id="free/gemini-4-hydrogen",
        quota_multiplier=5,
        supports_tools=True,
        supports_vision=True,
        verdict="mixing",
        verdict_badge="⚠",
        description="Most expensive (×5 quota); mixing",
        available=True,
    ),
    # ── Working but Avoid ───────────────────────────────────────────────────────
    ModelCatalogEntry(
        model_id="free/gpt-6-luna",
        quota_multiplier=3,
        supports_tools=True,
        supports_vision=True,
        verdict="avoid",
        verdict_badge="⚠",
        description="Avoid: answered Arabic questions in English",
        available=True,
    ),
    ModelCatalogEntry(
        model_id="free/kimi-k3",
        quota_multiplier=3,
        supports_tools=True,
        supports_vision=True,
        verdict="unavailable",
        verdict_badge="⛔",
        description="Avoid: heavy English/German mixing",
        available=False,
        unavailable_reason="HTTP 402: subscription only (re-tested 2026-11-23)",
    ),
    # ── Not Usable with this Key (402 Subscription / 400 No Chat) ──────────────
    ModelCatalogEntry(
        model_id="free/claude-opus-4.6",
        quota_multiplier=3,
        supports_tools=False,
        supports_vision=False,
        verdict="unavailable",
        verdict_badge="⛔",
        description="HTTP 402: subscription required",
        available=False,
        unavailable_reason="HTTP 402: available only with a subscription",
    ),
    ModelCatalogEntry(
        model_id="free/claude-sonnet-4.6",
        quota_multiplier=3,
        supports_tools=False,
        supports_vision=False,
        verdict="unavailable",
        verdict_badge="⛔",
        description="HTTP 402: subscription required",
        available=False,
        unavailable_reason="HTTP 402: available only with a subscription",
    ),
    ModelCatalogEntry(
        model_id="free/gemini-3.1-pro",
        quota_multiplier=3,
        supports_tools=False,
        supports_vision=False,
        verdict="unavailable",
        verdict_badge="⛔",
        description="HTTP 402: subscription required",
        available=False,
        unavailable_reason="HTTP 402: available only with a subscription",
    ),
    ModelCatalogEntry(
        model_id="free/glm-5.3",
        quota_multiplier=3,
        supports_tools=False,
        supports_vision=False,
        verdict="unavailable",
        verdict_badge="⛔",
        description="HTTP 402: subscription required",
        available=False,
        unavailable_reason="HTTP 402: available only with a subscription",
    ),
    ModelCatalogEntry(
        model_id="free/kimi-k2.8",
        quota_multiplier=3,
        supports_tools=False,
        supports_vision=False,
        verdict="unavailable",
        verdict_badge="⛔",
        description="HTTP 402: subscription required",
        available=False,
        unavailable_reason="HTTP 402: available only with a subscription",
    ),
    ModelCatalogEntry(
        model_id="free/minimax-m3",
        quota_multiplier=3,
        supports_tools=False,
        supports_vision=False,
        verdict="unavailable",
        verdict_badge="⛔",
        description="HTTP 402: subscription required",
        available=False,
        unavailable_reason="HTTP 402: available only with a subscription",
    ),
    ModelCatalogEntry(
        model_id="free/mimo-v2.6-flash",
        quota_multiplier=3,
        supports_tools=False,
        supports_vision=False,
        verdict="unavailable",
        verdict_badge="⛔",
        description="HTTP 402: subscription required",
        available=False,
        unavailable_reason="HTTP 402: available only with a subscription",
    ),
    ModelCatalogEntry(
        model_id="free/deepseek-v4-flash-0731",
        quota_multiplier=3,
        supports_tools=False,
        supports_vision=False,
        verdict="mixing",
        verdict_badge="⚠",
        description="Works again (2026-11-23); slow and mixes English words in alarm answers",
        available=True,
        unavailable_reason=None,
    ),
    ModelCatalogEntry(
        model_id="free/jev-1.13",
        quota_multiplier=1,
        supports_tools=False,
        supports_vision=False,
        verdict="unavailable",
        verdict_badge="⛔",
        description="HTTP 400: group decision model, no chat completions",
        available=False,
        unavailable_reason="HTTP 400: group decision model, no chat completions",
    ),
]

_CATALOG_INDEX: dict[str, ModelCatalogEntry] = {m.model_id: m for m in STATIC_MODEL_CATALOG}

# Runtime tracking of models that fail with 400 / 402:
_RUNTIME_UNAVAILABLE_MODELS: dict[str, str] = {
    m.model_id: m.unavailable_reason or "unavailable"
    for m in STATIC_MODEL_CATALOG
    if not m.available
}


def mark_model_unavailable(model_id: str, reason: str = "HTTP 400/402 failure") -> None:
    """Mark a model as runtime unavailable (e.g. after receiving HTTP 400 or 402)."""
    _RUNTIME_UNAVAILABLE_MODELS[model_id] = reason


def mark_model_available(model_id: str) -> None:
    """Mark a model as available (e.g. after successful test)."""
    _RUNTIME_UNAVAILABLE_MODELS.pop(model_id, None)


def is_model_available(model_id: str) -> bool:
    """Check if a model is currently available (not marked runtime unavailable)."""
    return model_id not in _RUNTIME_UNAVAILABLE_MODELS


def get_model_metadata(model_id: str) -> ModelCatalogEntry:
    """Get metadata for a model, accounting for runtime availability state."""
    base = _CATALOG_INDEX.get(model_id)
    if not base:
        # Fallback metadata for dynamic models not in static benchmark
        is_avail = model_id not in _RUNTIME_UNAVAILABLE_MODELS
        return ModelCatalogEntry(
            model_id=model_id,
            quota_multiplier=1,
            supports_tools=False,
            supports_vision=False,
            verdict="mixing" if is_avail else "unavailable",
            verdict_badge="?" if is_avail else "⛔",
            description="Listed by APInex. Capabilities and account access are unverified.",
            available=is_avail,
            unavailable_reason=_RUNTIME_UNAVAILABLE_MODELS.get(model_id),
        )

    is_avail = model_id not in _RUNTIME_UNAVAILABLE_MODELS
    return ModelCatalogEntry(
        model_id=base.model_id,
        quota_multiplier=base.quota_multiplier,
        supports_tools=base.supports_tools,
        supports_vision=base.supports_vision,
        verdict=base.verdict if is_avail else "unavailable",
        verdict_badge=base.verdict_badge if is_avail else "⛔",
        description=base.description,
        available=is_avail,
        unavailable_reason=_RUNTIME_UNAVAILABLE_MODELS.get(model_id, base.unavailable_reason),
    )


def get_model_catalog(dynamic_model_ids: list[str] | None = None) -> list[ModelCatalogEntry]:
    """Return the complete model catalog, merging static entries and any dynamic IDs."""
    seen = set()
    result: list[ModelCatalogEntry] = []

    for entry in STATIC_MODEL_CATALOG:
        seen.add(entry.model_id)
        result.append(get_model_metadata(entry.model_id))

    if dynamic_model_ids:
        for mid in dynamic_model_ids:
            if mid not in seen:
                seen.add(mid)
                result.append(get_model_metadata(mid))

    return result


def get_available_models(dynamic_model_ids: list[str] | None = None) -> list[str]:
    """Return list of model IDs that are currently available."""
    all_models = [m.model_id for m in STATIC_MODEL_CATALOG]
    if dynamic_model_ids:
        for mid in dynamic_model_ids:
            if mid not in all_models:
                all_models.append(mid)
    return [mid for mid in all_models if is_model_available(mid)]


def reset_unavailable_cache() -> None:
    """Reset runtime unavailable cache to initial static state (primarily for tests)."""
    _RUNTIME_UNAVAILABLE_MODELS.clear()
    for m in STATIC_MODEL_CATALOG:
        if not m.available:
            _RUNTIME_UNAVAILABLE_MODELS[m.model_id] = m.unavailable_reason or "unavailable"
