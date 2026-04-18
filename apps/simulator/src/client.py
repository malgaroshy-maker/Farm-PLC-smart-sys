"""HTTP and WebSocket client connecting simulator to backend API."""

import asyncio
import json

import httpx

from .engine import SimulatorEngine
from .state import FarmSimulationState, SimZoneState, SimPumpState


class APIClient:
    """Client for pulling pending commands and pushing live state."""
    
    def __init__(self, engine: SimulatorEngine, base_url: str = "http://127.0.0.1:8000/api/v1"):
        self.engine = engine
        self.base_url = base_url
        self.client = httpx.AsyncClient(base_url=self.base_url)
        self.running = False
        
    async def fetch_initial_layout(self):
        """Fetch real zones/pumps from DB to seed simulation state."""
        try:
            resp = await self.client.get("/zones")
            if resp.status_code == 200:
                zones = resp.json()
                for z in zones:
                    self.engine.state.zones[z["id"]] = SimZoneState(
                        zone_id=z["id"],
                        last_updated=self.engine.state.system.last_updated if hasattr(self.engine.state.system, 'last_updated') else __import__('datetime').datetime.utcnow()
                    )
            
            resp_p = await self.client.get("/pumps")
            if resp_p.status_code == 200:
                pumps = resp_p.json()
                for p in pumps:
                    self.engine.state.pumps[p["id"]] = SimPumpState(
                        pump_id=p["id"],
                        last_updated=__import__('datetime').datetime.utcnow()
                    )
            print(f"Seeded simulator: {len(self.engine.state.zones)} zones, {len(self.engine.state.pumps)} pumps.")
        except Exception as e:
            print(f"Could not fetch initial layout: {e}")

    async def poll_commands(self):
        """Poll API for pending commands and dispatch to engine."""
        try:
            resp = await self.client.get("/commands/pending")
            if resp.status_code == 200:
                commands = resp.json()
                if not commands:
                    return
                # Process strictly internally
                results = self.engine.process_commands(commands)
                # Sync results back to API
                for res in results:
                    cid = res.pop("command_id")
                    await self.client.patch(f"/commands/{cid}/sync", json=res)
        except Exception as e:
            print(f"Error polling commands: {e}")

    async def push_state(self):
        """Push memory state to /api/v1/state/sync."""
        try:
            payloads = self.engine.state.get_sync_payloads()
            await self.client.post("/state/sync", json=payloads)
        except Exception as e:
            print(f"Error pushing state: {e}")

    async def run_loop(self):
        """Worker loop managing communications."""
        self.running = True
        print(f"API Client started, connecting to {self.base_url}")
        
        await self.fetch_initial_layout()
        
        while self.running:
            # Poll commands
            await self.poll_commands()
            
            # Push state
            await self.push_state()
            
            # Rate limit the API interactions to 1Hz
            await asyncio.sleep(1.0)
