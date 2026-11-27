"""HTTP client connecting the simulator to the backend API (acts as the PLC bridge)."""

import asyncio
import json

import httpx

from .adapter import Layout
from .engine import SimulatorEngine
from .state import SimPumpState, SimSensorState, SimValveState, SimZoneState, ZoneConfig, utcnow

SENSOR_METRICS = {
    "sensor_tank_level": "tank_level_pct",
    "sensor_main_pressure": "main_pressure_bar",
    "sensor_main_flow": "main_flow_m3h",
}


class APIClient:
    """Gateway between the API and the farm controller (Milestone G3).

    Pulls pending commands and pushes live state, authenticated with the service token.
    The farm side is a ControllerAdapter: the simulator today, OPC UA (S7 PLC) later.
    Passing a SimulatorEngine still works (it is wrapped in a SimulatorAdapter).
    """

    def __init__(
        self,
        controller,
        base_url: str = "http://127.0.0.1:8000/api/v1",
        token: str = "dev-simulator-token",
        initial_timescale: float = 1.0,
    ):
        from .adapters.simulator_adapter import SimulatorAdapter

        if isinstance(controller, SimulatorEngine):
            controller = SimulatorAdapter(controller)
        self.adapter = controller
        self.engine = getattr(controller, "engine", None)  # simulator only (tests, scenarios)
        self.base_url = base_url
        self.token = token
        self.initial_timescale = initial_timescale
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=5.0,
        )
        self.running = False
        root = base_url.replace("/api/v1", "")
        ws_proto = "wss://" if root.startswith("https://") else "ws://"
        host_part = root.split("://", 1)[1] if "://" in root else root
        self.ws_host = host_part
        self.ws_url = f"{ws_proto}{host_part}/ws"

    async def sync_clock(self) -> None:
        try:
            resp = await self.client.get("/sim/clock")
            if resp.status_code == 200:
                data = resp.json()
                self._handle_clock_update(data)
                if (
                    self.initial_timescale != 1.0
                    and self.adapter.name == "simulator"
                    and data.get("mode") == "real"
                    and data.get("speed") == 1.0
                ):
                    set_resp = await self.client.post(
                        "/sim/clock", json={"speed": self.initial_timescale}
                    )
                    if set_resp.status_code == 200:
                        self._handle_clock_update(set_resp.json())
        except Exception as e:
            print(f"[GATEWAY] Could not sync clock: {e}")

    def _handle_clock_update(self, payload: dict) -> None:
        self.adapter.on_clock(payload)

    async def ws_loop(self) -> None:
        import websockets

        while self.running:
            try:
                async with websockets.connect(self.ws_url) as ws:
                    await ws.send(json.dumps({"type": "auth", "token": self.token}))
                    print(f"[SIMULATOR] Connected to WebSocket at {self.ws_host}")
                    while self.running:
                        msg = await ws.recv()
                        try:
                            data = json.loads(msg)
                            event_type = data.get("type")
                            payload = data.get("payload") or {}
                            if event_type in ("clock.changed", "state.snapshot"):
                                self._handle_clock_update(payload)
                        except Exception as e:
                            print(f"[GATEWAY] WS message error: {e}")
            except Exception:
                await asyncio.sleep(2.0)

    async def fetch_initial_layout(self) -> bool:
        """Load zones, pumps, valves and sensors from the API and start the adapter."""
        try:
            responses = {}
            for path in ("/zones", "/pumps", "/valves", "/sensors"):
                r = await self.client.get(path)
                r.raise_for_status()
                responses[path.strip("/")] = r.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (401, 403):
                print("API rejected the gateway token — check SIMULATOR_TOKEN matches the API.")
            else:
                print(f"Could not fetch layout: {e}")
            return False
        except httpx.HTTPError as e:
            print(f"API not reachable yet ({e.__class__.__name__}); retrying…")
            return False
        try:
            await self.adapter.start(Layout(**responses))
        except Exception as e:
            print(f"[GATEWAY] {self.adapter.name} adapter could not start: {e}")
            return False
        return True

    def comms_dropped(self) -> bool:
        return not self.adapter.link_ok()

    async def poll_commands(self) -> None:
        try:
            resp = await self.client.get("/commands/pending")
            resp.raise_for_status()
            updates = await self.adapter.execute(resp.json())
            for res in updates + await self.adapter.drain_events():
                cid = res.pop("command_id")
                await self.client.patch(f"/commands/{cid}/sync", json=res)
        except httpx.HTTPError as e:
            print(f"Error polling commands: {e!r}")

    async def push_state(self) -> None:
        try:
            payloads = await self.adapter.read_state()
            if not payloads:
                return
            resp = await self.client.post("/state/sync", json=payloads)
            resp.raise_for_status()
            if hasattr(self.adapter, "api_contact"):
                self.adapter.api_contact()
        except httpx.HTTPError as e:
            print(f"Error pushing state: {e!r}")

    async def refresh_fallback(self, force: bool = True) -> None:
        """G7: hand the controller today's program so it can irrigate if the app goes down."""
        if not hasattr(self.adapter, "load_fallback"):
            return
        try:
            resp = await self.client.get("/schedules/upcoming", params={"hours": 24})
            resp.raise_for_status()
            runs = resp.json()
            wanted = [(r["zone_id"], r["scheduled_start_farm"], r["duration_min"]) for r in runs]
            if not force and wanted == getattr(self, "_fallback_loaded", None):
                return
            await self.adapter.load_fallback(runs)
            self._fallback_loaded = wanted
        except httpx.HTTPError as e:
            print(f"Could not refresh the fallback program: {e!r}")

    async def run_loop(self) -> None:
        self.running = True
        print(f"Gateway ({self.adapter.name}) started, connecting to {self.base_url}")

        while self.running and not await self.fetch_initial_layout():
            await asyncio.sleep(2.0)

        await self.sync_clock()
        loop = asyncio.get_running_loop()
        ws_task = loop.create_task(self.ws_loop())

        try:
            ticks = 0
            while self.running:
                if not self.comms_dropped():
                    await self.poll_commands()
                    await self.push_state()
                    # a skipped or edited program must reach the controller within half a
                    # minute; the full reload every ~5 min covers a restarted controller
                    if ticks % 30 == 0:
                        await self.refresh_fallback(force=ticks % 300 == 0)
                elif hasattr(self.adapter, "probe"):
                    await self.adapter.probe()  # a real link went down: keep knocking
                ticks += 1
                await asyncio.sleep(1.0)
        finally:
            ws_task.cancel()
            await self.adapter.stop()


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
