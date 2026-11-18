"""HTTP client connecting the simulator to the backend API (acts as the PLC bridge)."""

import asyncio

import httpx

from .engine import SimulatorEngine
from .state import SimPumpState, SimZoneState, utcnow


class APIClient:
    """Pulls pending commands and pushes live state, authenticated with the service token."""

    def __init__(
        self,
        engine: SimulatorEngine,
        base_url: str = "http://127.0.0.1:8000/api/v1",
        token: str = "dev-simulator-token",
    ):
        self.engine = engine
        self.base_url = base_url
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=5.0,
        )
        self.running = False

    async def fetch_initial_layout(self) -> bool:
        """Seed simulation state from the API's zones and pumps. Returns True on success."""
        try:
            zones = await self.client.get("/zones")
            pumps = await self.client.get("/pumps")
            zones.raise_for_status()
            pumps.raise_for_status()
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (401, 403):
                print("API rejected the simulator token — check SIMULATOR_TOKEN matches the API.")
            else:
                print(f"Could not fetch layout: {e}")
            return False
        except httpx.HTTPError as e:
            print(f"API not reachable yet ({e.__class__.__name__}); retrying…")
            return False

        now = utcnow()
        for z in zones.json():
            self.engine.state.zones.setdefault(
                z["id"], SimZoneState(zone_id=z["id"], last_updated=now)
            )
        for p in pumps.json():
            self.engine.state.pumps.setdefault(
                p["id"], SimPumpState(pump_id=p["id"], last_updated=now)
            )
        print(
            f"Seeded simulator: {len(self.engine.state.zones)} zones, "
            f"{len(self.engine.state.pumps)} pumps."
        )
        return True

    async def poll_commands(self) -> None:
        try:
            resp = await self.client.get("/commands/pending")
            resp.raise_for_status()
            commands = resp.json()
            if not commands:
                return
            for res in self.engine.process_commands(commands):
                cid = res.pop("command_id")
                await self.client.patch(f"/commands/{cid}/sync", json=res)
        except httpx.HTTPError as e:
            print(f"Error polling commands: {e}")

    async def push_state(self) -> None:
        try:
            resp = await self.client.post("/state/sync", json=self.engine.state.get_sync_payloads())
            resp.raise_for_status()
        except httpx.HTTPError as e:
            print(f"Error pushing state: {e}")

    async def run_loop(self) -> None:
        self.running = True
        print(f"API Client started, connecting to {self.base_url}")

        while self.running and not await self.fetch_initial_layout():
            await asyncio.sleep(2.0)

        while self.running:
            await self.poll_commands()
            await self.push_state()
            await asyncio.sleep(1.0)
