# Farm PLC program (Milestone G5)

TIA Portal source files for the farm PLC: ET 200SP CPU 1512SP-1 PN, all SCL. Design: [docs/PLC_PROGRAM.md](../docs/PLC_PROGRAM.md).

**Status (2026-11-24):** **compiles in TIA Portal V19 with 0 errors and 0 warnings.** The TIA project is `AlgaroshyFarm` (projects root of TiaCommander).

**Bench closeout (2026-11-26).** PLCSIM Advanced passed all 13 eligible scenarios over Modbus at 1×, including the mainline leak. The two accelerated scenarios are marked incompatible with PLCSIM. A separate one-minute schedule passed at 1×. The local Unified HMI displayed ALM-013 and passed flashing, acknowledgement, and clear checks for ALM-005 and ALM-013. Arabic localization and HMI permissions are deferred. [Acceptance record](../docs/MILESTONE_G5_CLOSEOUT_PLAN.md)

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
- **Initial PLCSIM scenario suite (2026-11-24): 12 of 15 passed.** Normal cycle, direct-well cycle, tank critical, booster failed start, booster trip, valve failed to open, valve failed to close, repeated fault, no flow, emergency stop, comms loss and reset passed. The initial run left the leak and two accelerated schedule scenarios open. Running the suite found:
  - **Fixed (app):** a start without a duration was refused by the PLC (`plc_rejected`; the simulator used the zone default). The API now always sends the zone's default duration.
  - **Fixed (app):** one Modbus timeout stopped the gateway for good; it now reconnects (see `docs/CONTROLLER_ADAPTER.md`).
  - **Fixed (scenarios):** the prep waits until no zone is starting, running or stopping, because a PLC zone takes the valve travel time (10 s) to stop and refuses a new start until then. The comms-loss scenario waits for the controller to come back, not a fixed 20 s. A refused command now shows its reason in the scenario log.
  - **Fixed (owner, 2026-11-24): the alarm reset reaches the PLC.** Every reset in the Alarm Center also queues a `reset_alarm` command. The PLC holds a failed pump start (ALM-006/007) and the dry-run lock-out (ALM-027) until it gets one, so the Reset button shows on those alarms even while they are active. One click clears the PLC latch and the alarm. The scenario prep does the same.
  - **Fixed (PLC):** a zone stopped by a pump trip set the pump's alarm bit for its 30 s fault hold, so ALM-005 stayed active after the pump was repaired. Pump and system alarm bits now come only from their own source.
  - **Fixed (app):** a slow Modbus reply is retried once on a fresh connection before the link is marked down.
  - **Decided (owner, 2026-11-24): valve faults are detected by flow, no limit switches.** A valve that fails to open shows as no flow (ALM-012, the same as a blocked lateral). A valve that fails to close is caught when a zone stops: water still flowing with every valve commanded shut faults the zone with ALM-020 and the pump stops. The valve scenarios accept ALM-019 (simulator) or ALM-012 (PLC) for a stuck-closed valve.
  - **Fixed (scenarios):** a failed clock-speed scenario left the farm clock at 60x, so the farm's real programs fired every few minutes and started zones in the middle of other scenarios. The runner now restores the clock speed. The prep also waits for the PLC's zone fault (reported for 30 s) to clear before resetting alarms.
- **HMI (2026-11-25): built and tested live.** `FarmHMI` (MTP1000 Unified Comfort) has six screens made by `tools/tia/build_hmi.py` (see [docs/HMI_BUILD_GUIDE.md](../docs/HMI_BUILD_GUIDE.md)); the notes below are from the first HMI step, when the owner was to build the screens from the spec. PLC side done: `DB_HMI` buttons (`BtnStart`, `BtnStop`, `BtnStopAll`, `BtnReset`) become commands on the HMI channel in `FB_Link`, with the PLC's answer in `ResultOk`, `ResultText`, `ResultSeq`. Tested in PLCSIM: Start runs zone 1 with run source 4 (hmi), Stop all stops it.
- **Plant bridge note:** `PlcsimBridge` now reads the data-block tags too (`ETagListDetails.IOMDB`); without it new DB members were `DoesNotExist` after a download. Rebuild the exe after pulling.

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

**Bench check (2026-11-27), PLCSIM Advanced over Modbus, 11 of 11:**
- Pressing HMI **Stop all** (by writing `DB_HMI.BtnStopAll`) during a two-step program stopped the first zone, the app recorded a PLC stop and cancelled the program, and the second zone never started. The app's own STOP ALL left the HMI count unchanged.
- Starts for two different zones sent together on the HMI and OPC UA channels started exactly one zone in 6 of 6 trials. The test cannot force both into the same scan.
- Only the changed blocks were imported (`DB_Farm`, `03`, `06`, `11`). **Do not re-import `02_Data.db` whole into the bench project:** it resets `DB_Config` and with it the approved flow limits.
- **After a download that reinitializes data blocks, restart the CPU (STOP, then RUN).** Modbus port 502 stayed closed with `DB_Modbus.ServerStatus` = `16#80A3` until the restart, most likely because the old connection was still held.

**Second bench pass (2026-11-27):**
- 13/13 scenarios; Stop all and zone limit 11/11; HMI **Stop all** touched in the Unified runtime ended the app's program.
- Power cut, fallback and clock 15/15. Found and fixed: a stop during a power cut did not cancel the resume; nothing set the PLC clock.
- **The PLCSIM clock runs a few percent slow and can be hours off after a pause.** The gateway now corrects it; by hand, set the instance's `SystemTime` through the PLCSIM Advanced API.
- OPC UA (anonymous, no security, SIMATIC OPC UA small licence, then switched off again): the adapter passed 14/14 once the tag map numbered arrays from 0. Turning the server on assigned its certificate by itself.

## Load approved zone flow limits

Generate a separate `02_Config.db` in a staging folder. The exporter reads the app's existing zone fields by PLC zone ID and validates the bands against the mainline meter range. It leaves the farm database and checked-in PLC defaults untouched.

```powershell
# Run from the repository root. Supply a new output file in an existing folder.
python tools/tia/export_flow_config.py --bench <staging-folder>/02_Config.db
python tools/tia/export_flow_config.py --approved-database <approved-app.db> <staging-folder>/02_Config.db
```

- **PLCSIM only.** The owner approved 2–6 m³/h per zone for the bench. The simulated plant models 4 m³/h healthy and 10 m³/h with the fault applied. Field limits require measured flows and owner approval before export.
- Import the staged `DB_Config` and compile. After the approved download, read back `DB_Config.Zone[n].Id`, `.FlowMinM3h`, and `.FlowMaxM3h` for every mapped zone. If the running PLC still holds old retained limits, wait until the zones and pumps are idle, apply the approved values to those members in the online watch table, and repeat the readback before running a zone. On PLCSIM, the simulation API can perform the same check.
- Run one zone at a time. Check healthy flow, a pulse shorter than `BandTripS`, a sustained leak that raises ALM‑013 and closes the valve and stops the booster, and a restart after clearing the leak. Confirm the PLC alarm in the app and Unified runtime. Rerun `no_flow` and `valve_failed_close` after the change.

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
