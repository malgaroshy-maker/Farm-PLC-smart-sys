"""Feature switches (Milestone G3): turn features on/off from the Settings page, no code change.

Stored in `feature_flags`; read through a small in-memory cache so hot paths (monitor
tick, every chat call) don't hit the database. Unknown keys are rejected.
"""

import logging
import time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.timeutil import utcnow
from app.models.feature_flag import FeatureFlag

log = logging.getLogger(__name__)

# key -> (default, group). Groups match the Settings tabs.
FEATURES: dict[str, tuple[bool, str]] = {
    "ai.chat": (True, "ai"),
    "ai.alarm_explain": (True, "ai"),
    "ai.advisor": (True, "ai"),
    "ai.briefing": (True, "ai"),
    "map.weather_overlay": (True, "map"),
    "map.farm_life": (True, "map"),
    "map.irrigation_animation": (True, "map"),
    "automation.scheduler": (True, "automation"),
    "automation.advisor_auto": (True, "automation"),
    "automation.anomaly": (True, "automation"),
    "notify.in_app": (True, "notify"),
    # off until the owner configures them (token / keys)
    "notify.telegram": (False, "notify"),
    "notify.web_push": (False, "notify"),
}

_cache: dict[str, bool] = {}
_cache_at = 0.0
CACHE_SEC = 5.0


class UnknownFeature(KeyError):
    pass


async def _load(db: AsyncSession) -> dict[str, bool]:
    global _cache, _cache_at
    rows = (await db.execute(select(FeatureFlag))).scalars().all()
    stored = {r.key: r.enabled for r in rows}
    _cache = {k: stored.get(k, d) for k, (d, _g) in FEATURES.items()}
    _cache_at = time.monotonic()
    return _cache


async def all_features(db: AsyncSession, *, fresh: bool = False) -> dict[str, bool]:
    if fresh or not _cache or time.monotonic() - _cache_at > CACHE_SEC:
        return dict(await _load(db))
    return dict(_cache)


async def is_enabled(db: AsyncSession, key: str) -> bool:
    if key not in FEATURES:
        raise UnknownFeature(key)
    try:
        return (await all_features(db))[key]
    except Exception as exc:  # pragma: no cover - a DB hiccup must not switch features off
        log.warning("feature lookup failed (%s); using default for %s", exc, key)
        return FEATURES[key][0]


async def set_feature(db: AsyncSession, key: str, enabled: bool, by: str | None) -> dict[str, bool]:
    if key not in FEATURES:
        raise UnknownFeature(key)
    row = await db.get(FeatureFlag, key)
    if row is None:
        row = FeatureFlag(key=key)
        db.add(row)
    row.enabled = enabled
    row.updated_at = utcnow()
    row.updated_by = by
    await db.commit()
    return await all_features(db, fresh=True)


def clear_cache() -> None:
    global _cache, _cache_at
    _cache = {}
    _cache_at = 0.0
