"""Adapter #1: the physics simulator (demo). Wraps SimulatorEngine behind ControllerAdapter."""

from datetime import datetime

from ..adapter import Layout
from ..engine import SimulatorEngine
from ..state import utcnow


class SimulatorAdapter:
    name = "simulator"

    def __init__(self, engine: SimulatorEngine):
        self.engine = engine
        self._comms_down = False

    async def start(self, layout: Layout) -> None:
        from ..client import apply_layout

        apply_layout(self.engine, layout.zones, layout.pumps, layout.valves, layout.sensors)
        s = self.engine.state
        print(
            f"Seeded simulator: {len(s.zones)} zones, {len(s.pumps)} pumps, "
            f"{len(s.valves)} valves, {len(s.sensors)} sensors."
        )

    async def stop(self) -> None:
        return None

    async def read_state(self) -> list[dict]:
        return self.engine.state.get_sync_payloads()

    async def execute(self, commands: list[dict]) -> list[dict]:
        return self.engine.process_commands(commands)

    async def drain_events(self) -> list[dict]:
        return self.engine.drain_outbox()

    def link_ok(self) -> bool:
        until = self.engine.state.faults.comms_drop_until
        down = until is not None and utcnow() < until
        if down != self._comms_down:
            print("Comms DROPPED (simulated)" if down else "Comms restored")
            self._comms_down = down
        return not down

    def on_clock(self, payload: dict) -> None:
        """Follow the API's virtual farm clock (speed, pause, jump, step)."""
        speed = payload.get("speed")
        paused = payload.get("paused")
        if paused is None:
            paused = payload.get("clock_paused", False)
        action = payload.get("action")
        farm_now_str = payload.get("farm_now")
        if farm_now_str:
            try:
                dt = datetime.fromisoformat(farm_now_str.replace("Z", "+00:00"))
                gap = (dt - self.engine.sim_time).total_seconds()
                threshold = max(300.0, 5.0 * max(1.0, self.engine.timescale))
                if action == "step":
                    if 0 < gap <= 300:
                        self.engine.manual_step(gap)
                    self.engine.sim_time = dt
                elif action in ("jump", "reset") or abs(gap) > threshold:
                    self.engine.jump(dt)
                else:
                    self.engine.sim_time = dt
            except Exception:
                pass
        if speed is not None:
            self.engine.timescale = float(speed)
        self.engine.paused = bool(paused)
