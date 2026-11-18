"""Test setup: isolated SQLite DB, seeded farm, helpers to act as users or the simulator."""

import asyncio
import os
import tempfile
from pathlib import Path

_tmp = Path(tempfile.mkdtemp(prefix="farm-tests-"))
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{(_tmp / 'test.db').as_posix()}"
os.environ["SIMULATOR_TOKEN"] = "test-sim-token"
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "admin-pass"
os.environ["APP_ENV"] = "test"
os.environ["MONITOR_INTERVAL_SEC"] = "3600"  # don't let the background loop interfere

import bcrypt  # noqa: E402
import pytest  # noqa: E402

_gensalt = bcrypt.gensalt
bcrypt.gensalt = lambda rounds=4, prefix=b"2b": _gensalt(4, prefix)  # fast hashes in tests

from fastapi.testclient import TestClient  # noqa: E402

from app.core.security import hash_password  # noqa: E402
from app.core.timeutil import utcnow  # noqa: E402
from app.database import async_session_factory, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402
from app.models.user import User  # noqa: E402
from app.seed import ZONES, seed_database  # noqa: E402

SIM = {"Authorization": "Bearer test-sim-token"}
ZONE_IDS = [z["id"] for z in ZONES]


async def _reset_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    await seed_database(admin_password="admin-pass", verbose=False)
    async with async_session_factory() as s:
        for uid, role in (("user_operator", "operator"), ("user_viewer", "viewer")):
            s.add(
                User(
                    id=uid,
                    username=role,
                    name=role.title(),
                    role=role,
                    password_hash=hash_password(f"{role}-pass"),
                )
            )
        await s.commit()


@pytest.fixture()
def client():
    asyncio.run(_reset_db())
    with TestClient(app) as c:
        yield c


def login(client: TestClient, username: str) -> dict[str, str]:
    r = client.post(
        "/api/v1/auth/login", json={"username": username, "password": f"{username}-pass"}
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def push_state(
    client: TestClient,
    *,
    mode: str = "auto",
    tank: float = 90.0,
    zone_states: dict[str, str] | None = None,
    pump_fault: bool = False,
) -> None:
    """Act as the simulator and push a live-state snapshot."""
    now = utcnow().isoformat()
    zone_states = zone_states or {}
    payloads = [
        {"device_key": "system_mode", "state_json": {"mode": mode}, "updated_at": now},
        {
            "device_key": "simulation_stats",
            "state_json": {"tank_level_pct": tank, "main_pressure_bar": 0, "main_flow_m3h": 0},
            "updated_at": now,
        },
    ]
    for zid in ZONE_IDS:
        payloads.append(
            {
                "device_key": f"zone_{zid}",
                "state_json": {
                    "zone_id": zid,
                    "state": zone_states.get(zid, "off"),
                    "health": "healthy",
                    "runtime_sec": 0,
                    "last_updated": now,
                },
                "updated_at": now,
            }
        )
    for pid in ("pump_well_01", "pump_booster_01"):
        payloads.append(
            {
                "device_key": f"pump_{pid}",
                "state_json": {
                    "pump_id": pid,
                    "state": "faulted" if pump_fault else "stopped",
                    "fault": pump_fault,
                    "last_updated": now,
                },
                "updated_at": now,
            }
        )
    r = client.post("/api/v1/state/sync", json=payloads, headers=SIM)
    assert r.status_code == 200, r.text
