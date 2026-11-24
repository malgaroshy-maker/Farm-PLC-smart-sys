# Farm PLC program (Milestone G5)

TIA Portal source files for the farm PLC: ET 200SP CPU 1512SP-1 PN, all SCL. Design: [docs/PLC_PROGRAM.md](../docs/PLC_PROGRAM.md).

**Status (2026-11-24):** **compiles in TIA Portal V19 with 0 errors and 0 warnings.** The TIA project is `AlgaroshyFarm` (projects root of TiaCommander).
- **Hardware:** CPU 1512SP-1 PN **6ES7 512-1DM03-0AB0, firmware V3.1**, with the modules from design §2 and a server module. The I/O addresses match `tags.md`. `Farm_IO.tags.xml` is the tag table, ready for TiaCommander `tag import_table`.
  - It is the current 1512SP-1 PN: 400 KB code, 25 ns bit operation time. The older 6ES7 512-1DK01 stops at V2.9.
  - PLCSIM Advanced V6 only accepts firmware 3.1 (its virtual CPU reports "S31.23"). A V2.8 project is refused as incompatible.
- **Protection:** from firmware 2.9, TIA requires the *confidential PLC configuration data* password, and the owner sets it. Access level: full access for now (owner's choice). Tighten it before the real farm.
- **Running in PLCSIM Advanced V6** (2026-11-24), at 192.168.0.1, Modbus TCP on port 502. Verified:
  - The PLC heartbeat counts and the register map is correct.
  - With all inputs at 0 the PLC reacts as designed: E-stop active, no mains, tank critical so refilling, well dry. Exactly ALM-002, 027, 033 and 041 are set.
  - The **production Modbus adapter** drives it. A start is refused with `estop_active`; a stop and an alarm reset go through the seq/ack handshake.
  - **Fallback:** with no app heartbeat, the fallback schedule turns on after 120 s (ALM-029 set) and turns off again on the first heartbeats.
- **PLCSIM set-up that works:**
  - Instance with **PLC family ET 200SP** (an S7-1500 instance refuses this CPU type).
  - **TCP/IP Single Adapter**, IP 192.168.0.1/24. The PLCSIM virtual adapter is at 192.168.0.100.
  - The first download from the TIA window, to trust the PLC's certificate (firmware 3.x secure communication). After that, TiaCommander downloads work.
  - Windows services `almservice`, `s7oiehsx64` (S7DOS) and `SIMATIC PnDiscovery Service` must be running.
- **Found in PLCSIM and fixed:** the 1-second tick used `IN := NOT #tTick.Q`. On an S7-1500, reading `.Q` updates the timer, so it reset in the same scan and the tick never fired. Without the tick, the link watchdog and the fallback could never start.
- **Found in PLCSIM and fixed:** `FB_Farm` read the alarm-reset request before the command channels set it, so the pumps and the well lock-out never saw a reset (ALM-027 stayed latched). The reset is now read after the link block.
- **Plant bridge (our farm simulator around the real PLC):** `run.bat demo plcsim` (or `node scripts/start.mjs demo plcsim`).
  - `tools/plcsim/PlcsimBridge.exe` attaches to the PLCSIM instance through the PLCSIM Advanced API and serves its tags on `127.0.0.1:1600`. Build it once with the .NET Framework `csc` (command at the top of `PlcsimBridge.cs`); the exe is not committed.
  - `apps/simulator/src/plcsim_plant.py` reads the PLC's outputs (valve bytes, pump starts) every 200 ms, steps a farm model (pump feedback after 1.5 s, flow, pressure, tank, well, filter) and writes the inputs back, analogs as 4-20 mA raw values.
  - The app talks to the PLC as on the farm: Modbus TCP to 192.168.0.1. The Simulator page's panel switches and faults go to the farm model, so the PLC sees them as input changes.
  - Settings: `PLCSIM_HOST` (default 192.168.0.1), `PLCSIM_INSTANCE` (the instance name in PLCSIM, default `PLC`), `PLCSIM_BRIDGE_PORT` (default 1600).
  - Time runs at 1x: the PLC's timers are real time, so the simulation speed buttons do not speed it up.
- **Scenario suite on the real PLC (2026-11-24).** Normal cycle, direct-well cycle, tank critical, booster failed start, booster trip, emergency stop, comms loss and reset each pass on their own. Running the whole suite in a row found:
  - **Fixed (app):** a start without a duration was refused by the PLC (`plc_rejected`; the simulator used the zone default). The API now always sends the zone's default duration.
  - **Fixed (app):** one Modbus timeout stopped the gateway for good; it now reconnects (see `docs/CONTROLLER_ADAPTER.md`).
  - **Fixed (scenarios):** the prep waits until no zone is starting, running or stopping, because a PLC zone takes the valve travel time (10 s) to stop and refuses a new start until then. The comms-loss scenario waits for the controller to come back, not a fixed 20 s. A refused command now shows its reason in the scenario log.
  - **Open, needs the owner:**
    - The app never sends an alarm reset to the controller (`reset_alarm` is not implemented), so the PLC's latched failed start (ALM-006/007) and well lock-out (ALM-027) can't be cleared from the app.
    - Wired valves have no limit switch, so the PLC can't raise ALM-019/020 (valve failed to open or close). It sees a stuck valve only as no flow (ALM-012) or unexpected flow (ALM-021).
    - The PLC's per-zone flow and pressure limits are still the 1-30 m3/h defaults, so a mainline leak can't trip ALM-013 until each zone's limits are set.
    - The scheduled-day scenarios speed up the clock; a real PLC runs on real time, so they only run in simulator mode.
- **Next:** the open points above, then the HMI.

The first compile found three things the static checker can't catch, all fixed in the sources:
- an FC input `String` takes no length;
- a multi-instance FB needs at least one static member;
- `40000` overflows a 16-bit `Int` in a Modbus address.

## Files

| File | Content |
|---|---|
| `src/01_Types.udt` | `UDT_ZoneCfg`, `UDT_ZoneState`, `UDT_Pump`, `UDT_Run`, `UDT_CmdChannel` |
| `src/02_Data.db` | `DB_Config` (zones with today's ids, limits), `DB_Farm`, `DB_Zones`, `DB_Pumps`, `DB_Cmd`, `DB_Fallback`, `DB_Power`, `DB_Alarms`, `DB_Modbus`, `DB_HMI` |
| `src/03_Functions.scl` | Scaling, bit helper, zone-by-id, reason texts, **`FC_CanStart`** (the interlocks) |
| `src/04_Zone.scl` | `FB_Zone`: the zone state machine (same states as the app) |
| `src/05_Pump.scl` | `FB_Pump`: start, feedback, failed start, HAND/OFF/AUTO, runtime, energy |
| `src/06_Command.scl` | `FB_CmdChannel` (seq/ack handshake) and `FB_Link` (3 channels: OPC UA, Modbus, HMI; heartbeat watchdog → fallback) |
| `src/07_Power.scl` | `FB_Power`: power cut and the 30-minute resume rule, also across a PLC restart |
| `src/08_Fallback.scl` | `FB_Fallback`: runs the stored schedule while the app is away |
| `src/09_Hydraulics.scl` | `FB_Hydraulics`: pump demand, tank refill, flow share, trips, unexpected flow, well dry-run lock-out |
| `src/10_RadioBoxes.scl` | `FB_RadioBoxes`: Modbus RTU master for radio valve boxes (on-timer refresh) and energy meters |
| `src/11_ModbusMap.scl` | `FB_ModbusMap`: `MB_SERVER` on port 502 and the register image |
| `src/12_Alarms.scl` | `FB_Alarms`: alarm bits numbered like the app's catalog, reset, packing |
| `src/13_IO.scl` | `FC_ReadInputs`, `FC_WriteOutputs`: the only blocks that touch I/O |
| `src/14_Farm.scl` | `FB_Farm` (everything as multi-instances), its instance DB `iFarm`, and `Main` (OB1) |
| `tags.md` | The I/O tag table to create first |

## Import into TIA Portal (once licensed)

1. Project `AlgaroshyFarm`: add the CPU 1512SP-1 PN and the modules (design §2): `TiaTool add-device` / `plug`. With firmware ≥ V2.9, TIA requires the configuration-protection password, which the owner sets. Enable **Project properties → Support simulation during block compilation** (needed for PLCSIM Advanced).
2. Create the tag table **Farm_IO** from `tags.md`. Check that the system constants `Local~PROFINET_interface_1` and `Local~CM_PtP_1` exist under those names (PLC tags → System constants).
3. **External source files → Add new external file:** add all files in `src/` in number order, then **Generate blocks from source** in the same order: 01 → 02 → 03 … → 14. Or run `TiaTool import-sources <plc/src> [from-file]`, which does both.
4. Compile (hardware, then software). Fix what the compiler reports. The static checker below catches most mistakes, but not all of them.
5. Activate the OPC UA server; the Modbus TCP server starts from `FB_ModbusMap`.
6. Download to a PLCSIM Advanced instance in TCP/IP mode. Then follow the test plan in the design §8.

The helper `tools/tia/TiaTool.exe` (built from `tools/tia/TiaTool.cs`) can add the CPU and modules through Openness (`add-device`, `plug`, `project-set`), once the licence allows it.

## Static check

```
python tools/tia/scl_lint.py
```

It checks:
- block and `IF`/`CASE`/`FOR`/`REGION` pairing;
- missing `;`;
- undeclared `#locals`;
- unknown DBs, tags and functions;
- member names on DBs, UDTs, multi-instances and system types.

It does **not** check data types in expressions; the TIA compiler does that.

## Things to verify at the first compile

- `MB_SERVER` accepts the optimized `"DB_Modbus".HR` array (newer versions do). If not, make `DB_Modbus` a standard (non-optimized) DB.
- `Modbus_Comm_Load` / `Modbus_Master` instruction versions, and whether `MB_DB := #mbMaster.MB_DB` works with multi-instances.
- The radio-box register layout (`FB_RadioBoxes`) must match the relay board actually bought.
