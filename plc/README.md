# Farm PLC program (Milestone G5)

TIA Portal source files for the farm PLC: ET 200SP CPU 1512SP-1 PN, all SCL. Design: [docs/PLC_PROGRAM.md](../docs/PLC_PROGRAM.md).

**Status:** written and statically checked, but **not compiled yet**. TIA Portal on the development PC has no active STEP 7 licence (`Necessary license 'STEP 7 Professional' is missing`). Import, compile and the PLCSIM tests come once the licence works.

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

1. Project `AlgaroshyFarm`: add the CPU 1512SP-1 PN and the modules (design §2). Set the configuration-protection password yourself. Enable **Project properties → Support simulation during block compilation** (needed for PLCSIM Advanced).
2. Create the tag table **Farm_IO** from `tags.md`. Check that the system constants `Local~PROFINET_interface_1` and `Local~CM_PtP_1` exist under those names (PLC tags → System constants).
3. **External source files → Add new external file:** add all files in `src/` in number order, then **Generate blocks from source** in the same order: 01 → 02 → 03 … → 14.
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
