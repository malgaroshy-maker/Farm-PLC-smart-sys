"""Soil moisture (Milestone G7).

Everything in the app uses **% of available water**: 0 % = wilting point (the tree can't drink),
100 % = field capacity (soil holds all it can). Probes report volumetric water content (VWC %);
`relative()` converts it with the zone's soil limits (sandy-loam defaults below).

Start/stop levels come per crop (`crop_moisture_levels`), and a zone can override them. Soil logic
(skip a full zone, stop early, dry alerts and extra-run suggestions) only acts on **confirmed**
levels: the owner reviews the proposed numbers first. A zone override counts as confirmed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.timeutil import as_utc, utcnow
from app.models.soil import CropMoistureLevel
from app.models.zone import Zone
from app.services.live_state import Snapshot

DEFAULT_FC_VWC = 18.0  # sandy loam field capacity, VWC %
DEFAULT_WP_VWC = 7.0  # sandy loam wilting point, VWC %
PROBE_FRESH = timedelta(hours=3)  # a wireless probe reports every 10–60 min
PROBE_FAULT_AFTER = timedelta(hours=6)  # ALM-016 when a probe goes silent this long
FEATURE = "automation.soil"


def relative(vwc: float, fc: float | None = None, wp: float | None = None) -> float:
    """VWC % → % of available water (clamped to 0–120 so over-watering stays visible)."""
    fc = fc or DEFAULT_FC_VWC
    wp = wp if wp is not None else DEFAULT_WP_VWC
    if fc <= wp:
        return 0.0
    return round(max(0.0, min(120.0, (vwc - wp) / (fc - wp) * 100.0)), 1)


@dataclass
class ZoneSoil:
    zone_id: str
    moisture: float | None  # % available water, None when no usable reading
    source: str  # probe | controller | none
    start: float
    stop: float
    confirmed: bool

    @property
    def state(self) -> str:
        if self.moisture is None:
            return "unknown"
        if self.moisture < self.start:
            return "dry"
        if self.moisture >= self.stop:
            return "full"
        return "ok"


def _fresh(ts: str | None, now: datetime, within: timedelta) -> bool:
    if not ts:
        return False
    try:
        return now - as_utc(datetime.fromisoformat(str(ts).replace("Z", "+00:00"))) <= within
    except ValueError:
        return False


def probe_readings(
    snapshots: dict[str, Snapshot], now: datetime | None = None
) -> dict[str, list[dict]]:
    """External soil probes (posted by the gateway), fresh ones only, grouped by zone."""
    now = now or utcnow()
    out: dict[str, list[dict]] = {}
    for key, snap in snapshots.items():
        st = snap.state
        if key.startswith("sensor_") and st.get("external") and st.get("zone_id"):
            if st.get("quality") == "good" and _fresh(st.get("timestamp"), now, PROBE_FRESH):
                out.setdefault(st["zone_id"], []).append(st)
    return out


def zone_moisture(
    snapshots: dict[str, Snapshot], zone_id: str, now: datetime | None = None
) -> tuple[float | None, str]:
    """Root-zone moisture: the average of the zone's fresh probes, else the controller's value."""
    probes = probe_readings(snapshots, now).get(zone_id)
    if probes:
        return round(sum(float(p["value"]) for p in probes) / len(probes), 1), "probe"
    z = snapshots.get(f"zone_{zone_id}")
    if z is not None and z.state.get("moisture_pct") is not None:
        return float(z.state["moisture_pct"]), "controller"
    return None, "none"


# Proposed starting levels (% available water); the owner confirms or edits them in Settings.
PROPOSED = {
    "olives": (40.0, 85.0),
    "pomegranate": (50.0, 90.0),
    "grapes": (45.0, 85.0),
    "mixed_fruit": (55.0, 90.0),
    "other": (50.0, 90.0),
}


async def levels(db: AsyncSession) -> dict[str, CropMoistureLevel]:
    rows = {r.crop_type: r for r in (await db.execute(select(CropMoistureLevel))).scalars()}
    missing = [c for c in PROPOSED if c not in rows]
    for crop in missing:  # a fresh database: add the proposed, unconfirmed levels
        start, stop = PROPOSED[crop]
        rows[crop] = CropMoistureLevel(
            crop_type=crop, start_pct=start, stop_pct=stop, confirmed=False
        )
        db.add(rows[crop])
    if missing:
        await db.flush()
    return rows


async def zone_levels(
    db: AsyncSession, zone: Zone, crop_levels: dict | None = None
) -> tuple[float, float, bool]:
    crop_levels = crop_levels if crop_levels is not None else await levels(db)
    row = crop_levels.get(zone.crop_type) or crop_levels.get("other")
    start = (
        zone.moisture_start_pct
        if zone.moisture_start_pct is not None
        else (row.start_pct if row else 50.0)
    )
    stop = (
        zone.moisture_stop_pct
        if zone.moisture_stop_pct is not None
        else (row.stop_pct if row else 90.0)
    )
    overridden = zone.moisture_start_pct is not None and zone.moisture_stop_pct is not None
    return start, stop, overridden or bool(row and row.confirmed)


async def soil_status(db: AsyncSession, snapshots: dict[str, Snapshot]) -> dict[str, ZoneSoil]:
    crop_levels = await levels(db)
    zones = (await db.execute(select(Zone).where(Zone.enabled.is_(True)))).scalars().all()
    out = {}
    for z in zones:
        moisture, source = zone_moisture(snapshots, z.id)
        start, stop, confirmed = await zone_levels(db, z, crop_levels)
        out[z.id] = ZoneSoil(z.id, moisture, source, start, stop, confirmed)
    return out


async def logic_on(db: AsyncSession) -> bool:
    from app.services.features import is_enabled

    return await is_enabled(db, FEATURE)


DRY_LOOKAHEAD_H = 12


async def dry_without_run(db: AsyncSession, status: dict[str, ZoneSoil]) -> list[ZoneSoil]:
    """Confirmed zones below their start level with no run in the next 12 hours."""
    dry = [s for s in status.values() if s.confirmed and s.state == "dry"]
    if not dry:
        return []
    from app.routers.schedules import compute_upcoming_runs  # lazy: avoid an import cycle

    planned = {r.zone_id for r in await compute_upcoming_runs(db, DRY_LOOKAHEAD_H)}
    return [s for s in dry if s.zone_id not in planned]
