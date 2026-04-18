"""Core deterministic physics & state machine engine."""

import asyncio
from datetime import datetime, timedelta

import json

from .state import FarmSimulationState
from .scenarios import FaultInjector


class SimulatorEngine:
    """Deterministic simulation loop."""

    def __init__(self, state: FarmSimulationState, timescale: float = 1.0):
        self.state = state
        self.timescale = timescale  # 1.0 = real-time, 60.0 = 1 real sec is 1 sim minute
        self.running = False
        self.faults = FaultInjector(self.state)

    def process_commands(self, commands: list[dict]) -> list[dict]:
        """Process incoming commands, update state, and return updates for sync."""
        updates = []
        now = datetime.utcnow()
        for cmd in commands:
            ctype = cmd.get("command_type")
            tid = cmd.get("target_id")
            
            status = "completed"
            reason = None
            
            try:
                if ctype == "start_zone":
                    if tid in self.state.zones:
                        z = self.state.zones[tid]
                        z.state = "starting_pump"
                        z.runtime_sec = 0
                        z.last_updated = now
                    else:
                        status = "failed"
                        reason = f"Zone {tid} not found"
                elif ctype == "stop_zone":
                    if tid in self.state.zones:
                        z = self.state.zones[tid]
                        z.state = "stopping"
                        z.last_updated = now
                    else:
                        status = "failed"
                        reason = f"Zone {tid} not found"
                elif ctype == "set_mode":
                    payload = json.loads(cmd.get("payload_json", "{}")) if cmd.get("payload_json") else {}
                    self.state.system.system_mode = payload.get("mode", "auto")
                elif ctype == "inject_fault":
                    payload = json.loads(cmd.get("payload_json", "{}")) if cmd.get("payload_json") else {}
                    success, msg = self.faults.handle_fault_command(payload)
                    if not success:
                        status = "failed"
                        reason = msg
                else:
                    status = "rejected"
                    reason = "Unknown command type"
            except Exception as e:
                status = "failed"
                reason = str(e)
                
            updates.append({
                "command_id": cmd.get("id"),
                "status": status,
                "completed_at": now.isoformat() if status == "completed" else None,
                "failure_reason": reason
            })
            
        return updates

    async def tick(self, dt: float):
        """Simulate one time slice. dt is simulated seconds elapsed."""
        now = datetime.utcnow()
        
        # 1. Pump physics
        running_pumps = [p for p in self.state.pumps.values() if p.state == "running"]
        if running_pumps:
            self.state.system.main_pressure_bar = min(6.0, len(running_pumps) * 3.0)
            # Drain tank slowly if using tank
            self.state.system.tank_level_pct = max(0.0, self.state.system.tank_level_pct - (0.01 * dt * len(running_pumps)))
        else:
            self.state.system.main_pressure_bar = max(0.0, self.state.system.main_pressure_bar - (0.5 * dt))
            
        total_flow = 0.0
        
        # 2. Zone state machine & physics
        for zone in self.state.zones.values():
            if zone.state == "starting_pump":
                # Find a pump and start it
                for p in self.state.pumps.values():
                    if p.state in ["stopped", "cooldown"]:
                        p.state = "starting"
                        p.last_updated = now
                        break
                zone.state = "opening_valve"
                zone.last_updated = now
                
            elif zone.state == "opening_valve":
                # Wait for valve to open
                zone.state = "running"
                zone.last_updated = now
                
            elif zone.state == "running":
                zone.runtime_sec += dt
                # Increase moisture
                zone.moisture_pct = min(100.0, zone.moisture_pct + (0.05 * dt))
                zone.flow_m3h = 15.0 if self.state.system.main_pressure_bar > 2.0 else 5.0
                zone.pressure_bar = self.state.system.main_pressure_bar - 0.5
                zone.last_updated = now
                total_flow += zone.flow_m3h
                
            elif zone.state == "stopping":
                zone.flow_m3h = 0.0
                zone.pressure_bar = 0.0
                zone.state = "completed"
                zone.last_updated = now
                # Stop pump if no other zones
                any_running = any(z.state in ["starting_pump", "opening_valve", "running", "validating_flow"] for z in self.state.zones.values())
                if not any_running:
                    for p in self.state.pumps.values():
                        if p.state == "running":
                            p.state = "stopped"
                            p.last_updated = now

        self.state.system.main_flow_m3h = total_flow

        # 3. Complete pump startups
        for p in self.state.pumps.values():
            if p.state == "starting":
                p.state = "running"
                p.run_fb = True
                p.last_updated = now
            elif p.state == "running":
                p.runtime_hours += dt / 3600.0

    async def run_loop(self):
        """Main async loop."""
        print(f"Simulator Engine started. Timescale: {self.timescale}x")
        self.running = True
        
        # We target 1 real-time tick per second
        tick_interval = 1.0
        
        while self.running:
            start_time = asyncio.get_event_loop().time()
            
            # Simulated elapsed time is real tick_interval * timescale
            # Example: tick_interval=1s, timescale=60 means 60 simulated seconds pass every real second
            dt = tick_interval * self.timescale
            
            await self.tick(dt)
            
            # Wait remainder of the 1-second interval
            elapsed = asyncio.get_event_loop().time() - start_time
            sleep_time = max(0, tick_interval - elapsed)
            await asyncio.sleep(sleep_time)
