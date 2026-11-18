"""
Seed script — Load 12-zone Algaroshy Farm data into the database.

Usage:
    cd apps/api
    alembic upgrade head      # create / migrate tables first
    python -m app.seed

The admin password comes from ADMIN_PASSWORD; if it is empty a random one is
generated and printed once.

Seeds match the TypeScript contracts in packages/contracts/src/seeds.ts.
"""

import asyncio
import secrets

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.config import settings
from app.core.security import hash_password
from app.database import async_session_factory
from app.models.farm import Farm
from app.models.pump import Pump
from app.models.sensor import Sensor
from app.models.user import User
from app.models.valve import Valve
from app.models.water_source import WaterSource
from app.models.zone import Zone

# ── Farm ─────────────────────────────────────────────────

FARM = {
    "id": "farm_algaroshy",
    "name": "Algaroshy Farm",
    "name_ar": "مزرعة الجروشي",
    "description": "Smart automated irrigation system for Algaroshy Farm",
    "timezone": "Africa/Tripoli",
    "total_area_ha": 11.90,
}

# ── 12 Zones ─────────────────────────────────────────────

ZONES = [
    {
        "id": "zone_rumman_1",
        "code": "RUMMAN_1",
        "name": "Pomegranate 1",
        "name_ar": "رمان 1",
        "crop_type": "pomegranate",
        "area_ha": 0.50,
        "priority": 1,
        "allows_direct_well": False,
        "max_runtime_min": 90,
        "default_duration_min": 45,
        "flow_min_m3h": 2.0,
        "flow_max_m3h": 8.0,
    },
    {
        "id": "zone_rumman_2",
        "code": "RUMMAN_2",
        "name": "Pomegranate 2",
        "name_ar": "رمان 2",
        "crop_type": "pomegranate",
        "area_ha": 0.71,
        "priority": 2,
        "allows_direct_well": False,
        "max_runtime_min": 90,
        "default_duration_min": 60,
        "flow_min_m3h": 3.0,
        "flow_max_m3h": 10.0,
    },
    {
        "id": "zone_rumman_3",
        "code": "RUMMAN_3",
        "name": "Pomegranate 3",
        "name_ar": "رمان 3",
        "crop_type": "pomegranate",
        "area_ha": 0.54,
        "priority": 3,
        "allows_direct_well": False,
        "max_runtime_min": 90,
        "default_duration_min": 45,
        "flow_min_m3h": 2.5,
        "flow_max_m3h": 8.0,
    },
    {
        "id": "zone_rumman_4",
        "code": "RUMMAN_4",
        "name": "Pomegranate 4",
        "name_ar": "رمان 4",
        "crop_type": "pomegranate",
        "area_ha": 0.71,
        "priority": 4,
        "allows_direct_well": True,
        "max_runtime_min": 90,
        "default_duration_min": 60,
        "flow_min_m3h": 3.0,
        "flow_max_m3h": 10.0,
    },
    {
        "id": "zone_rumman_5",
        "code": "RUMMAN_5",
        "name": "Pomegranate 5",
        "name_ar": "رمان 5",
        "crop_type": "pomegranate",
        "area_ha": 0.64,
        "priority": 5,
        "allows_direct_well": False,
        "max_runtime_min": 90,
        "default_duration_min": 50,
        "flow_min_m3h": 2.5,
        "flow_max_m3h": 9.0,
    },
    {
        "id": "zone_rumman_6",
        "code": "RUMMAN_6",
        "name": "Pomegranate 6",
        "name_ar": "رمان 6",
        "crop_type": "pomegranate",
        "area_ha": 0.81,
        "priority": 6,
        "allows_direct_well": False,
        "max_runtime_min": 120,
        "default_duration_min": 60,
        "flow_min_m3h": 3.0,
        "flow_max_m3h": 11.0,
    },
    {
        "id": "zone_rumman_ummahat",
        "code": "RUMMAN_UMMAHAT",
        "name": "Pomegranate Mothers",
        "name_ar": "رمان امهات",
        "crop_type": "pomegranate",
        "area_ha": 0.14,
        "priority": 7,
        "allows_direct_well": True,
        "max_runtime_min": 60,
        "default_duration_min": 30,
        "flow_min_m3h": 1.0,
        "flow_max_m3h": 4.0,
    },
    {
        "id": "zone_rumman_jadeed",
        "code": "RUMMAN_JADEED",
        "name": "New Pomegranate",
        "name_ar": "رمان جديد",
        "crop_type": "pomegranate",
        "area_ha": 0.93,
        "priority": 8,
        "allows_direct_well": True,
        "max_runtime_min": 120,
        "default_duration_min": 60,
        "flow_min_m3h": 3.5,
        "flow_max_m3h": 12.0,
    },
    {
        "id": "zone_zaytoun",
        "code": "ZAYTOUN",
        "name": "Olives",
        "name_ar": "زيتون",
        "crop_type": "olives",
        "area_ha": 2.29,
        "priority": 9,
        "allows_direct_well": False,
        "max_runtime_min": 180,
        "default_duration_min": 90,
        "flow_min_m3h": 5.0,
        "flow_max_m3h": 18.0,
    },
    {
        "id": "zone_zaytoun_2",
        "code": "ZAYTOUN_2",
        "name": "Olives 2",
        "name_ar": "زيتون 2",
        "crop_type": "olives",
        "area_ha": 0.15,
        "priority": 10,
        "allows_direct_well": True,
        "max_runtime_min": 60,
        "default_duration_min": 30,
        "flow_min_m3h": 1.0,
        "flow_max_m3h": 4.0,
    },
    {
        "id": "zone_enab",
        "code": "ENAB",
        "name": "Grapes",
        "name_ar": "عنب",
        "crop_type": "grapes",
        "area_ha": 0.07,
        "priority": 11,
        "allows_direct_well": True,
        "max_runtime_min": 45,
        "default_duration_min": 20,
        "flow_min_m3h": 0.5,
        "flow_max_m3h": 3.0,
    },
    {
        "id": "zone_fruit_mix",
        "code": "FRUIT_MIX",
        "name": "Peach + Apricot + Plum",
        "name_ar": "خوخ + مشمش + عوينة",
        "crop_type": "mixed_fruit",
        "area_ha": 1.09,
        "priority": 12,
        "allows_direct_well": True,
        "max_runtime_min": 120,
        "default_duration_min": 60,
        "flow_min_m3h": 4.0,
        "flow_max_m3h": 14.0,
    },
]

# ── Pumps ────────────────────────────────────────────────

PUMPS = [
    {
        "id": "pump_well_01",
        "code": "WELL_PUMP_01",
        "name": "Well Pump",
        "name_ar": "مضخة البئر",
        "pump_type": "well",
        "service_interval_hours": 2000,
    },
    {
        "id": "pump_booster_01",
        "code": "BOOSTER_PUMP_01",
        "name": "Booster Pump",
        "name_ar": "مضخة التعزيز",
        "pump_type": "booster",
        "service_interval_hours": 2000,
    },
]

# ── Water Sources ────────────────────────────────────────

SOURCES = [
    {"id": "src_tank", "name": "Main Water Tank", "name_ar": "خزان المياه الرئيسي", "type": "tank"},
    {
        "id": "src_well",
        "name": "Farm Well (Direct)",
        "name_ar": "بئر المزرعة (مباشر)",
        "type": "well_direct",
    },
]

# ── Mainline Sensors ─────────────────────────────────────

MAINLINE_SENSORS = [
    {
        "id": "sensor_tank_level",
        "code": "TANK_LEVEL_01",
        "sensor_type": "level",
        "unit": "%",
        "location_scope": "tank",
    },
    {
        "id": "sensor_main_pressure",
        "code": "MAIN_PRESSURE_01",
        "sensor_type": "pressure",
        "unit": "bar",
        "location_scope": "mainline",
    },
    {
        "id": "sensor_main_flow",
        "code": "MAIN_FLOW_01",
        "sensor_type": "flow",
        "unit": "m³/h",
        "location_scope": "mainline",
    },
]


async def seed_database(
    session_factory: async_sessionmaker = async_session_factory,
    admin_password: str | None = None,
    verbose: bool = True,
) -> str | None:
    """Insert seed data. Returns the admin password if one was generated."""
    log = print if verbose else (lambda *a, **k: None)
    password = admin_password or settings.admin_password
    generated = None
    if not password:
        password = generated = secrets.token_urlsafe(12)

    async with session_factory() as session:
        # Check if already seeded
        result = await session.execute(select(Farm).where(Farm.id == FARM["id"]))
        if result.scalar_one_or_none():
            log("⚠️  Database already seeded. Skipping.")
            return None

        # ── Farm ─────────────────────────────────────────
        farm = Farm(**FARM)
        session.add(farm)
        log(f"✅ Farm: {FARM['name']}")

        # ── Default Admin User ───────────────────────────
        admin = User(
            id="user_admin",
            username=settings.admin_username,
            name="Mahamed Algaroshy",
            email="admin@algaroshy.farm",
            role="owner_admin",
            is_active=True,
            password_hash=hash_password(password),
        )
        session.add(admin)
        log(f"✅ Admin user created: {settings.admin_username}")

        # ── Zones (12) ──────────────────────────────────
        for z in ZONES:
            zone = Zone(
                farm_id="farm_algaroshy",
                source_preference="tank",
                pressure_min_bar=1.5,
                pressure_max_bar=4.0,
                **z,
            )
            session.add(zone)
        log(f"✅ {len(ZONES)} zones seeded")

        # ── Valves (one per zone) ────────────────────────
        for z in ZONES:
            valve = Valve(
                id=f"valve_{z['code'].lower()}",
                zone_id=z["id"],
                code=f"VALVE_{z['code']}",
                enabled=True,
                has_open_feedback=True,
                has_close_feedback=True,
            )
            session.add(valve)
        log(f"✅ {len(ZONES)} valves seeded")

        # ── Pumps ────────────────────────────────────────
        for p in PUMPS:
            pump = Pump(
                farm_id="farm_algaroshy",
                runtime_hours=0.0,
                enabled=True,
                **p,
            )
            session.add(pump)
        log(f"✅ {len(PUMPS)} pumps seeded")

        # ── Water Sources ────────────────────────────────
        for s in SOURCES:
            src = WaterSource(
                enabled=True,
                availability="available",
                **s,
            )
            session.add(src)
        log(f"✅ {len(SOURCES)} water sources seeded")

        # ── Mainline Sensors ─────────────────────────────
        for s in MAINLINE_SENSORS:
            sensor = Sensor(
                farm_id="farm_algaroshy",
                zone_id=None,
                enabled=True,
                **s,
            )
            session.add(sensor)

        # ── Zone Moisture Sensors (12) ───────────────────
        for z in ZONES:
            sensor = Sensor(
                id=f"sensor_moisture_{z['code'].lower()}",
                farm_id="farm_algaroshy",
                zone_id=z["id"],
                code=f"MOISTURE_{z['code']}",
                sensor_type="moisture",
                unit="%",
                location_scope="zone",
                enabled=True,
            )
            session.add(sensor)
        log(f"✅ {len(MAINLINE_SENSORS) + len(ZONES)} sensors seeded")

        # ── Commit ───────────────────────────────────────
        await session.commit()
        log("\n🌾 Seed complete! Algaroshy Farm is ready.")
        log(f"   Zones: {len(ZONES)}")
        log(f"   Pumps: {len(PUMPS)}")
        log(f"   Valves: {len(ZONES)}")
        log(f"   Sensors: {len(MAINLINE_SENSORS) + len(ZONES)}")
        log(f"   Sources: {len(SOURCES)}")
        if generated:
            log(f"\n🔑 Generated admin password (shown once): {generated}")
            log("   Set ADMIN_PASSWORD in .env to choose your own.")
    return generated


if __name__ == "__main__":
    import sys

    # Windows consoles/pipes default to cp1252, which can't print the emoji above.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    asyncio.run(seed_database())
