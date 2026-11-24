"""What the OPC UA and Modbus adapters share for the real farm PLC (G5, docs/PLC_PROGRAM.md).

The PLC numbers things; the app names them. This module is the one place that translates.
"""

from __future__ import annotations

from datetime import datetime

# FB_Zone states (UDT_ZoneState.State) -> the app's zone states
ZONE_STATES = (
    "off",
    "starting_pump",
    "opening_valve",
    "validating_flow",
    "running",
    "stopping",
    "completed",
    "faulted",
    "interrupted",
)
RUN_SOURCES = {0: "app", 1: "panel", 2: "fallback", 3: "resume", 4: "hmi"}
PANEL_ZONE = {0: "auto", 1: "on", 2: "off"}
PANEL_PUMP = {0: "auto", 1: "hand", 2: "off"}
MODES = {0: "off", 1: "auto", 2: "manual", 3: "maintenance"}
REASONS = {
    1: "interlock",
    2: "zone_in_manual",
    3: "no_power",
    4: "pump_unavailable",
    5: "tank_low",
    6: "estop_active",
    7: "already_running",
    8: "bad_target",
    9: "plc_rejected",
}

# Alarms the app takes from the PLC (catalog source "plc"); the app derives the others itself.
SYSTEM_ALARMS = {2, 3, 13, 27, 33, 41}  # 13: mainline leak (also a zone fault)
PUMP_ALARMS = {4: "pump_well_01", 7: "pump_well_01", 5: "pump_booster_01", 6: "pump_booster_01"}
ZONE_FAULT_ALARMS = {12, 13, 19, 20, 33}


def zone_state(code: int) -> str:
    return ZONE_STATES[code] if 0 <= code < len(ZONE_STATES) else "off"


def alarm_bits(words: list[int]) -> set[int]:
    """DB_Alarms.Word0..2 -> alarm numbers (bit 0 of word 0 = ALM-001)."""
    out = set()
    for w_i, w in enumerate(words):
        for bit in range(16):
            if (int(w) >> bit) & 1:
                out.add(w_i * 16 + bit + 1)
    return out


def plc_alarms(active: set[int], zone_faults: dict[str, int]) -> list[dict]:
    """The `plc_alarms` payload, keyed the way the simulator reports them."""
    out = []
    for n in sorted(active):
        code = f"ALM-{n:03d}"
        if n in PUMP_ALARMS:
            out.append({"code": code, "device_id": PUMP_ALARMS[n], "zone_id": None})
        elif n in SYSTEM_ALARMS:
            out.append({"code": code, "device_id": None, "zone_id": None})
    for zid, n in zone_faults.items():
        if n in ZONE_FAULT_ALARMS:
            out.append({"code": f"ALM-{n:03d}", "device_id": None, "zone_id": zid})
    return out


def dtl_weekday(d: datetime) -> int:
    """DTL convention: 1 = Sunday .. 7 = Saturday."""
    return (d.weekday() + 1) % 7 + 1


def fallback_runs(
    runs: list[dict], zone_index: dict[str, int], limit: int
) -> list[tuple[int, int, int, int]]:
    """/schedules/upcoming rows -> (zone index, start minute of day, duration min, weekday)."""
    out = []
    for r in runs:
        try:
            start = datetime.fromisoformat(r["scheduled_start_farm"])
            z = zone_index[r["zone_id"]]
            dur = int(r["duration_min"])
        except (KeyError, ValueError, TypeError):
            continue
        out.append((z, start.hour * 60 + start.minute, dur, dtl_weekday(start)))
        if len(out) >= limit:
            break
    return out
