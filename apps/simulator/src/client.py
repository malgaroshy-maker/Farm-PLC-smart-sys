"""HTTP client connecting the simulator to the backend API (acts as the PLC bridge)."""

import asyncio
import json
from datetime import datetime

import httpx

from .engine import SimulatorEngine
from .state import SimPumpState, SimSensorState, SimValveState, SimZoneState, ZoneConfig, utcnow

SENSOR_METRICS = {
    "sensor_tank_level": "tank_level_pct",
    "sensor_main_pressure": "main_pressure_bar",
    "sensor_main_flow": "main_flow_m3h",
}


class APIClient:
    """Pulls pending commands and pushes live state, authenticated with the service token."""

    def __init__(
        self,
        engine: SimulatorEngine,
        base_url: str = "http://127.0.0.1:8000/api/v1",
        token: str = "dev-simulator-token",
        initial_timescale: float = 1.0,
    ):
        self.engine = engine
        self.base_url = base_url
        self.token = token
        self.initial_timescale = initial_timescale
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=5.0,
        )
        self.running = False
        self._comms_down = False
        root = base_url.replace("/api/v1", "")
        ws_proto = "wss://" if root.startswith("https://") else "ws://"
        host_part = root.split("://", 1)[1] if "://" in root else root
        self.ws_url = f"{ws_proto}{host_part}/ws?token={token}"

    async def sync_clock(self) -> None:
        try:
            resp = await self.client.get("/sim/clock")
            if resp.status_code == 200:
                data = resp.json()
                self._handle_clock_update(data)
                if (
                    self.initial_timescale != 1.0
                    and data.get("mode") == "real"
                    and data.get("speed") == 1.0
                ):
                    set_resp = await self.client.post(
                        "/sim/clock", json={"speed": self.initial_timescale}
                    )
                    if set_resp.status_code == 200:
                        self._handle_clock_update(set_resp.json())
        except Exception as e:
            print(f"[SIMULATOR] Could not sync clock: {e}")

    def _handle_clock_update(self, payload: dict) -> None:
        speed = payload.get("speed")
        paused = payload.get("paused")
        if paused is None:
            paused = payload.get("clock_paused", False)
        action = payload.get("action")
        farm_now_str = payload.get("farm_now")
        if farm_now_str:
            try:
                s = farm_now_str.replace("Z", "+00:00")
                dt = datetime.fromisoformat(s)
                gap = (dt - self.engine.sim_time).total_seconds()
                threshold = max(300.0, 5.0 * max(1.0, self.engine.timescale))
                if action in ("jump", "step") or abs(gap) > threshold:
                    self.engine.jump(dt)
                else:
                    self.engine.sim_time = dt
            except Exception:
                pass
        if speed is not None:
            self.engine.timescale = float(speed)
        self.engine.paused = bool(paused)

    async def ws_loop(self) -> None:
        import websockets

        while self.running:
            try:
                async with websockets.connect(self.ws_url) as ws:
                    print(f"[SIMULATOR] Connected to WebSocket at {self.ws_url}")
                    while self.running:
                        msg = await ws.recv()
                        try:
                            data = json.loads(msg)
                            event_type = data.get("type")
                            payload = data.get("payload") or {}
                            if event_type in ("clock.changed", "state.snapshot"):
                                self._handle_clock_update(payload)
                        except Exception as e:
                            print(f"[SIMULATOR] WS message error: {e}")
            except Exception:
                await asyncio.sleep(2.0)

    async def fetch_initial_layout(self) -> bool:
        """Load zones, pumps, valves and sensors from the API. Returns True on success."""
        try:
            responses = {}
            for path in ("/zones", "/pumps", "/valves", "/sensors"):
                r = await self.client.get(path)
                r.raise_for_status()
                responses[path] = r.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (401, 403):
                print("API rejected the simulator token — check SIMULATOR_TOKEN matches the API.")
            else:
                print(f"Could not fetch layout: {e}")
            return False
        except httpx.HTTPError as e:
            print(f"API not reachable yet ({e.__class__.__name__}); retrying…")
            return False

        apply_layout(self.engine, **{k.strip("/"): v for k, v in responses.items()})
        s = self.engine.state
        print(
            f"Seeded simulator: {len(s.zones)} zones, {len(s.pumps)} pumps, "
            f"{len(s.valves)} valves, {len(s.sensors)} sensors."
        )
        return True

    def comms_dropped(self) -> bool:
        until = self.engine.state.faults.comms_drop_until
        down = until is not None and utcnow() < until
        if down != self._comms_down:
            print("Comms DROPPED (simulated)" if down else "Comms restored")
            self._comms_down = down
        return down

    async def poll_commands(self) -> None:
        try:
            resp = await self.client.get("/commands/pending")
            resp.raise_for_status()
            updates = self.engine.process_commands(resp.json())
            for res in updates + self.engine.drain_outbox():
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

        await self.sync_clock()
        loop = asyncio.get_running_loop()
        ws_task = loop.create_task(self.ws_loop())

        try:
            while self.running:
                if not self.comms_dropped():
                    await self.poll_commands()
                    await self.push_state()
                await asyncio.sleep(1.0)
        finally:
            ws_task.cancel()


def apply_layout(engine: SimulatorEngine, zones, pumps, valves, sensors) -> None:
    """Build simulator config + live state from API records (also used by tests)."""
    s, now = engine.state, utcnow()
    valve_by_zone = {v["zone_id"]: v["id"] for v in valves}
    for z in zones:
        s.zone_cfg[z["id"]] = ZoneConfig(
            id=z["id"],
            code=z["code"],
            area_ha=z.get("area_ha") or 0.5,
            allows_direct_well=z.get("allows_direct_well", False),
            default_duration_min=z.get("default_duration_min", 45),
            max_runtime_min=z.get("max_runtime_min", 120),
            pressure_min_bar=z.get("pressure_min_bar", 1.5),
            pressure_max_bar=z.get("pressure_max_bar", 4.0),
            flow_min_m3h=z.get("flow_min_m3h", 2.0),
            flow_max_m3h=z.get("flow_max_m3h", 10.0),
            valve_id=valve_by_zone.get(z["id"]),
        )
        s.zones.setdefault(z["id"], SimZoneState(zone_id=z["id"], last_updated=now))
    for p in pumps:
        s.pumps.setdefault(
            p["id"],
            SimPumpState(
                pump_id=p["id"], pump_type=p.get("pump_type", "booster"), last_updated=now
            ),
        )
    for v in valves:
        s.valves.setdefault(
            v["id"], SimValveState(valve_id=v["id"], zone_id=v["zone_id"], last_updated=now)
        )
    for sen in sensors:
        metric = SENSOR_METRICS.get(sen["id"])
        if metric is None and sen.get("sensor_type") == "moisture" and sen.get("zone_id"):
            metric = f"moisture:{sen['zone_id']}"
        if metric:
            s.sensors.setdefault(
                sen["id"],
                SimSensorState(
                    sensor_id=sen["id"], metric_key=metric, unit=sen.get("unit", ""), timestamp=now
                ),
            )
