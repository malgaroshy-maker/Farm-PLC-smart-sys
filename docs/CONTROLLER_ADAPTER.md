# Controller adapter (Milestones G3 and G7)

The farm controller is connected through a **gateway** (`apps/simulator/src/client.py`). The gateway talks to the API:
- it loads the farm layout (zones, valves, pumps, sensors) from the database;
- it pushes live state to `/state/sync`, once a second;
- it pulls pending commands and reports their results.

The farm side is an **adapter** that implements `ControllerAdapter` (`apps/simulator/src/adapter.py`):

| Adapter | File | Used for |
|---|---|---|
| `simulator` (default) | `src/adapters/simulator_adapter.py` | The physics simulator: today's demo. |
| `opcua` | `src/adapters/opcua_adapter.py` | A Siemens S7-1200/1500 over OPC UA. **Skeleton:** the node ids come from the TIA Portal project in Milestone G5. |
| `modbus` (G7) | `src/adapters/modbus_adapter.py` | Any controller that speaks Modbus TCP: S7-200 SMART, LOGO! 8, Delta AS, or an S7-1200 without OPC UA. Needs no extra Python package. |

Select an adapter with environment variables:

```
CONTROLLER_ADAPTER=simulator          # default
CONTROLLER_ADAPTER=opcua              # needs:
OPCUA_TAGMAP=apps/simulator/opcua_tagmap.example.json
CONTROLLER_ADAPTER=modbus             # needs:
MODBUS_MAP=apps/simulator/modbus_map.example.json
```

## Safety rule
The PLC owns the interlocks. Adapters only forward commands; they never bypass or imitate the PLC's safety logic on the real hardware path. The API's own interlocks stay in place as a first check.

## OPC UA command handshake
1. The gateway writes `type`, `target` and `duration_min`, then increments `seq`.
2. The PLC checks its interlocks, then acts or refuses. It writes `ack_status` (1 = accepted, 2 = rejected) and `ack_reason`, then sets `ack_seq = seq`.
3. If no acknowledgement arrives within 5 s, the command is reported as `failed: plc_no_ack`.

Command types: `start_zone = 1`, `stop_zone = 2`, `stop_all = 3`, `reset_alarm = 4`.

A zone without tags in the tag map is reported as `failed: no_tags_for:<zone>`. The gateway never pretends a command succeeded.

## Modbus TCP register map (G7)
`modbus_map.example.json` lists one **16-bit holding register** per value (layout from the G5 PLC design: system 0–19, 16 zones at 100–259, pumps 270/280, command 300–307), using the 0-based address sent on the wire. Reads are signed, and `value = register / scale`, so `{"hr": 4, "scale": 10}` holding 725 means 72.5. Each zone also has an `index`, the number the PLC uses as the command target.

The handshake is the same as OPC UA, with numbers instead of text:
- `target` is the zone `index`; `stop_all` and `reset_alarm` send 0.
- `ack_reason` is a code: 1 interlock, 2 zone_in_manual, 3 no_power, 4 pump_unavailable, 5 tank_low, 6 estop_active, 9 other.
- The PLC runs a start for exactly `duration_min` on its own timer, so a lost link can never leave a valve open.

The client is a small built-in one (`src/modbus_tcp.py`, function codes 3, 6 and 16). The same file has a tiny register server for bench tests.

## Field readiness values (G7), for the G5 PLC program
The gateway reads these when the controller provides them. In OPC UA they are extra tags; in Modbus they are extra registers.

| Value | Where | Meaning |
|---|---|---|
| `power_ok` | system | 0 while the mains is off (UPS or battery only). The API blocks starts and raises ALM-033. |
| `fallback_active` | system | 1 while the PLC runs its own copy of today's schedule because the server is unreachable (over 120 s). |
| `well_level_m`, `filter_dp_bar` | system | Well water level and filter pressure drop. ALM-027 below 1.5 m (the PLC stops the well pump); ALM-039 above 0.5 bar. |
| `panel_mode` | zone | Panel switch: 0 auto, 1 on (hand), 2 off. In on/off the app cannot start or stop the zone; ALM-042 is shown. |
| `panel_mode` | pump | 0 auto, 1 hand, 2 off. Off counts as unavailable for starts. |
| `power_kw`, `current_a` | pump | From a power meter or the VFD. Shown on the Equipment page and the Dashboard. |

**Power-cut rule (owner):** after a cut, a zone that was running resumes only if the power was off for less than `POWER_RESUME_MAX_MIN` (30 min). Otherwise the run is skipped and an alarm is raised. The PLC applies this rule; the simulator shows it.

**Fallback program:** the gateway keeps the next 24 hours of runs (`/schedules/upcoming`) and hands them to the controller. If the server is unreachable for longer than `FALLBACK_AFTER_SEC`, the controller runs them by itself. When the link returns, the runs it made are recorded as unattended cycles. Today only the simulator adapter loads the fallback program; the PLC version is part of G5.

## Tests
`apps/simulator/tests/test_modbus_adapter.py` runs the adapter against the in-process register server. The server plays the PLC: it accepts a start, rejects a zone in manual, and in one test never answers. The test also checks scaling and what happens when the link is lost.

`apps/simulator/tests/test_opcua_adapter.py` starts a real in-process OPC UA server built from a tag map. That server answers the handshake the way the PLC will: it accepts a start, rejects an interlocked zone, and in a separate test stays silent so the no-ack path is covered. Validation against **PLCSIM Advanced** comes in G5, before any hardware.

## Adding a zone
Settings → Zones & equipment → Add a zone creates the zone, its valve and its moisture sensor in the database.
- **Controller:** the simulator picks the new zone up on its next start. For a PLC, add the zone's tags to the tag map (OPC UA), or its registers and `index` to the register map (Modbus).
- **Map:** the zone appears on the map once its outline is traced (`tools/map-geometry`).
