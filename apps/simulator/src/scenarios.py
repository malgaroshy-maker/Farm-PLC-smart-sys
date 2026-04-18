"""Scenario Runner and Fault Injection logic."""

import json


class FaultInjector:
    """Modifies simulation physics to reflect faults."""

    def __init__(self, state):
        self.state = state

    def handle_fault_command(self, payload: dict) -> tuple[bool, str]:
        """Process inject_fault commands.
        e.g. payload = {"target_type": "valve", "target_id": "v-1", "fault_type": "stuck_closed"}
        """
        try:
            target_type = payload.get("target_type")
            target_id = payload.get("target_id")
            fault_type = payload.get("fault_type")
            
            if target_type == "valve":
                if target_id in self.state.valves:
                    v = self.state.valves[target_id]
                    if fault_type == "stuck_closed":
                        v.status = "fault"
                        # In a real simulation, we'd alter the flow logic in engine.py based on this valve
                    elif fault_type == "clear":
                        v.status = v.last_command if v.last_command != "none" else "closed"
                    else:
                        return False, f"Unknown valve fault: {fault_type}"
                else:
                    return False, f"Valve {target_id} not found"
            
            elif target_type == "pump":
                if target_id in self.state.pumps:
                    p = self.state.pumps[target_id]
                    if fault_type == "trip":
                        p.state = "faulted"
                        p.fault = True
                        p.run_fb = False
                    elif fault_type == "clear":
                        p.state = "stopped"
                        p.fault = False
                    else:
                        return False, f"Unknown pump fault: {fault_type}"
                else:
                    return False, f"Pump {target_id} not found"
                    
            elif target_type == "system":
                if fault_type == "mainline_leak":
                    self.state.system.main_pressure_bar = max(0.0, self.state.system.main_pressure_bar - 2.0)
                else:
                    return False, f"Unknown system fault: {fault_type}"

            return True, "Fault injected"

        except Exception as e:
            return False, str(e)
