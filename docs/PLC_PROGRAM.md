# PLC program design (Milestone G5)

The design for the farm PLC program. It is built in TIA Portal V19, tested in PLCSIM Advanced V6 and connected to the app. It builds on [PLC_CONTROL_LOGIC.md](PLC_CONTROL_LOGIC.md) (rules), [IO_LIST.md](IO_LIST.md) (signals) and [CONTROLLER_ADAPTER.md](CONTROLLER_ADAPTER.md) (the link to the app).

**Status:** approved 2026-11-24. The PLC code lives as TIA source files in [plc/](../plc/README.md). It **compiles in TIA Portal V19 with no errors or warnings** (CPU 6ES7 512-1DM03-0AB0 at firmware V3.1, the version PLCSIM Advanced V6 simulates). The PLCSIM Advanced tests are next.

## 1. Owner decisions (2026-11-24)

| Topic | Decision |
|---|---|
| CPU | ET 200SP **CPU 1512SP-1 PN**, article **6ES7 512-1DM03-0AB0**, firmware V3.1 (S7-1500 family) |
| Link to the app | **Both** OPC UA and Modbus TCP. Each installation picks one (`CONTROLLER_ADAPTER`). |
| Language | **All SCL** |
| Zone valves | **Both** wired outputs and radio boxes (Modbus RTU over RS-485/LoRa), chosen per zone in a config DB |
| HMI | **MTP1000 Unified Comfort** (10"), Arabic + English switch |
| Scope | Tags, DBs and the handshake · zone and pump logic · G7 field rules · HMI |
| Zones | **16** (12 today + 4 spare): a new zone is config only |
| Panel switches | **3-position ON / AUTO / OFF** selector per zone and per pump (2 inputs each) |
| Plant for PLCSIM | **Our Python simulator** drives the PLC's inputs and reads its outputs through the PLCSIM Advanced API |

## 2. Hardware configuration (TIA project)

| Slot | Module | Use |
|---|---|---|
| 0 | CPU 1512SP-1 PN | Program, OPC UA server, Modbus TCP server (`MB_SERVER`), PROFINET to the HMI |
| 1 | DI 16×24 VDC ST | E-stop, mains-power-OK (UPS relay), pump run/fault feedback, pump panel switches |
| 2–3 | DI 16×24 VDC ST (×2) | Zone panel switches: 2 inputs per zone (ON, OFF; neither = AUTO) for 16 zones |
| 4 | DQ 16×24 VDC/0.5 A ST | 16 wired zone valves (via interposing relays or 24 V coils) |
| 5 | DQ 8×24 VDC/0.5 A ST | Well pump start, booster start, alarm beacon, horn, spares |
| 6 | AI 8×I 2-/4-wire ST | Tank level, main pressure, main flow, well level, filter ΔP (2 transmitters), spares |
| 7 | CM PtP (RS-485) | Modbus RTU master to the radio boxes (and an energy meter) |
| — | Server module | |
| PN | MTP1000 Unified Comfort | HMI over PROFINET/Ethernet |

Pump power (kW, A, kWh) comes from a Modbus energy meter on the same RS-485 line. Soil probes stay on the LoRaWAN gateway → app path (G7), not the PLC.

Final module part numbers and terminal assignments follow the hardware order. Wiring isn't decided here; the program only needs the counts above.

## 3. Program structure

| Block | Type | Job |
|---|---|---|
| `Main` | OB1 | Calls the blocks below in order, once per cycle |
| `Startup` | OB100 | Safe start: all outputs off, then reconcile (§6.6) |
| `Cyclic100ms` | OB30 | Timers that must not depend on the cycle time (power-cut clock, link watchdog) |
| `Diag` | OB82/OB86 | Module and rack faults → alarm |
| `FC_ReadInputs` | FC | Scale analogs (4–20 mA → units), debounce digital inputs, read panel switches |
| `FB_Link` | FB | App link: heartbeat watchdog, command handshake (§5), fallback switch-over |
| `FB_Interlocks` | FB | One `can_start(zone)` answer with a reason code (§6.2) |
| `FB_Zone` | FB ×16 (multi-instance) | Zone state machine (§6.1) |
| `FB_Pump` | FB ×2 | Pump start, run feedback, failed start, fault, runtime, panel switch |
| `FB_Hydraulics` | FB | Source choice (tank+booster or direct well), pressure/flow validation, unexpected flow |
| `FB_Power` | FB | Mains loss and the 30-minute resume rule (§6.4) |
| `FB_Fallback` | FB | Runs the stored schedule while the app is away (§6.5) |
| `FB_RadioBoxes` | FB | Modbus RTU master: sends valve commands with an on-timer to each radio box, reads its state |
| `FB_Alarms` | FB | Sets/latches alarm bits per code, shared with the app and the HMI |
| `FB_ModbusMap` | FB | `MB_SERVER` and copying live values into, and commands out of, the holding-register DB |
| `FC_WriteOutputs` | FC | The only place outputs are written: wired valves, pumps, beacon |

## 4. Data

### 4.1 Types (UDTs)
- `UDT_ZoneCfg`:
  - `Id` (String[24], e.g. `zone_rumman_1`), `Enabled`;
  - `ValveKind` (0 wired, 1 radio), `RadioBox`, `RadioCoil`;
  - `MaxRuntimeMin`, `FlowMin`, `FlowMax`, `PressMin`, `PressMax`;
  - `Source` (0 tank, 1 direct well allowed).
- `UDT_ZoneState`:
  - `State` (Int, §6.1), `RunSource` (0 app, 1 panel, 2 fallback, 3 resume);
  - `TargetSec`, `RuntimeSec`, `StartsToday`;
  - `Flow`, `Pressure`, `ValveOpenFb`, `PanelMode` (0 auto, 1 on, 2 off), `FaultCode`.
- `UDT_Pump`:
  - `CmdStart`, `RunFb`, `Fault`, `FailedStart`;
  - `PanelMode` (0 auto, 1 hand, 2 off);
  - `RuntimeHours`, `PowerKw`, `CurrentA`, `EnergyKwhToday`.
- `UDT_Run` (fallback): `ZoneIndex`, `StartMinOfDay`, `DurationMin`, `WeekdayMask`, `Valid`.

### 4.2 Data blocks
| DB | Content | Retain |
|---|---|---|
| `DB_Config` | `Zone[1..16]` of `UDT_ZoneCfg`, pump timeouts, tank limits, `PowerResumeMaxMin = 30`, `LinkTimeoutS = 120`, `WellDryM = 1.5` | Yes |
| `DB_Farm` | Mode, E-stop, `PowerOk`, `FallbackActive`, tank, main pressure/flow, well level, filter ΔP, heartbeat out | No |
| `DB_Zones` | `Zone[1..16]` of `UDT_ZoneState` | No |
| `DB_Pumps` | `Booster`, `Well` of `UDT_Pump` | Runtime/energy only |
| `DB_Cmd` | Handshake: `Seq`, `Type`, `Target`, `DurationMin`, `AckSeq`, `AckStatus`, `AckReason`, `AppHeartbeat` | No |
| `DB_Fallback` | `Run[1..48]` of `UDT_Run`, `LoadedAt`, `Count` | Yes |
| `DB_Alarms` | One Bool per alarm code (`ALM_021`, `ALM_027`, `ALM_033`, `ALM_042`, …), plus ack/reset | No |
| `DB_Modbus` | `HR[0..399]` Word: the Modbus register image | No |
| `DB_HMI` | HMI-only values: language, selected zone, start-duration entry | No |

All DBs are optimized. OPC UA is symbolic; Modbus reads only `DB_Modbus`.

## 5. Link to the app

### 5.1 OPC UA
The server exposes `DB_Farm`, `DB_Zones`, `DB_Pumps` and `DB_Cmd` (and `DB_Fallback` for writing). Node ids follow `ns=3;s="DB_Zones"."Zone"[1]."State"`. G5 replaces the placeholder ids in `opcua_tagmap.example.json` with these. No security in this milestone (owner: not chosen).

### 5.2 Modbus TCP
`MB_SERVER` on port 502 serves `DB_Modbus.HR`. The addresses are **exactly** those in `apps/simulator/modbus_map.example.json`: system 0–19, zone *n* at 100 + 10·(*n*−1) for 16 zones (100–259), pumps 270 and 280, command 300–307 (307 = app heartbeat), fallback runs 320+. The example becomes the real map. `FB_ModbusMap` copies live values in with the same scales.

### 5.3 Command handshake (both links)
1. The app writes `Type` (1 start, 2 stop, 3 stop all, 4 reset alarm), `Target` (zone index) and `DurationMin`, then `Seq + 1`.
2. On a new `Seq`, `FB_Link` asks `FB_Interlocks`. It then either starts/stops or refuses. It writes `AckStatus` (1 accepted / 2 rejected) and `AckReason`, then `AckSeq = Seq`, all in the same cycle.
3. Reason codes: 1 interlock, 2 zone_in_manual, 3 no_power, 4 pump_unavailable, 5 tank_low, 6 estop_active, 9 other. Over OPC UA the reason is also written as text, for the existing adapter.
4. A start always carries a duration. The PLC stops the zone on its own timer, so a lost link never leaves a valve open.

### 5.4 Heartbeat and fallback program (adapter work in G5)
- **App → PLC:** the gateway writes `DB_Cmd.AppHeartbeat` (a counter) every push. If it hasn't changed for `LinkTimeoutS` (120 s), the PLC sets `FallbackActive`.
- **Fallback schedule:** every 5 minutes, and after a schedule change, the gateway writes the next 24 hours of runs (from `/schedules/upcoming`) into `DB_Fallback`. Today only the simulator adapter does this; G5 adds it to the OPC UA and Modbus adapters. Modbus uses registers 320+: up to 48 runs × 4 words.

## 6. Logic

### 6.1 Zone state machine (`FB_Zone`)
States match the app: `off → starting_pump → opening_valve → validating_flow → running → stopping → completed`, plus `faulted` and `interrupted`.
- **Start:** the source pump runs (or is already running), then the valve opens: a wired DQ, or a radio command with an on-timer of duration + 2 min. Pressure and flow must reach the zone's band within the validation window, otherwise the zone goes to `faulted` with an alarm.
- **Stop:** the valve closes when the timer ends, on a stop command, an interlock trip or E-stop. The pump stops when no zone needs it.
- **Run checks:** a sustained out-of-band pressure or flow stops the zone. A short excursion only warns.

### 6.2 Interlocks (`FB_Interlocks`)
A start is refused, with its reason code, if:
- E-stop is active;
- the mains is off;
- the zone's panel switch is not on AUTO;
- the system mode is off;
- the zone is disabled or already running;
- the zone limit or combination is not allowed;
- the needed pump is faulted or its panel switch is OFF;
- the tank is critical with no direct-well path;
- the well is in dry-run lock-out.

The app keeps its own checks as a first filter. **The PLC's answer is final.**

### 6.3 Panel switches (G7)
- A zone switch on **ON** runs the zone (`RunSource = panel`) with no time limit. The pump follows, and every protection still trips it.
- **OFF** holds the valve closed.
- Either position raises ALM-042 (info) and refuses app commands for that zone with `zone_in_manual`.
- Pump **HAND** runs the pump with protections; **OFF** makes it unavailable.

### 6.4 Power cut (G7, owner rule)
The UPS keeps the PLC and the radio on. A "mains OK" relay feeds a DI. When the mains drops:
- every running zone becomes `interrupted` with its remaining time stored, valves close and ALM-033 is raised;
- an OB30 clock counts the outage.

When the mains returns:
- if the outage was **< 30 min** (`PowerResumeMaxMin`), each interrupted zone resumes its remaining time (`RunSource = resume`);
- otherwise it goes to `faulted` with "power was out N min, run not resumed".

### 6.5 Fallback program (G7)
While `FallbackActive`, `FB_Fallback` starts each run in `DB_Fallback` at its time, for its duration, through the normal zone logic and interlocks. Runs keep `RunSource = fallback`, so the app records them as unattended cycles when the link returns. These times are the PLC's own local clock, so the gateway sets it over Modbus whenever it is more than 5 s off farm time (registers 16–19 show it, 308–314 set it). The app raises ALM-051 if it stays more than 2 minutes off. Over OPC UA the clock is not set yet.

### 6.6 Restart (OB100)
- All outputs off, every zone `off`, and the radio boxes are sent "close".
- `FB_Power` treats the time the PLC was off as an outage, so the 30-minute rule applies to runs that were going before the restart. Their remaining time is kept in retain memory.

### 6.7 Protection
- **Well dry run (ALM-027):** well level < 1.5 m stops the well pump and locks it out until the level recovers by 0.5 m and the alarm is reset.
- **Filter ΔP > 0.5 bar (ALM-039):** a warning only.
- **Unexpected flow (ALM-021):** flow > 0.8 m³/h with no zone open for 30 s.
- **Pump failed start, trip, valve faults:** the existing alarm codes in [ALARM_MATRIX.md](ALARM_MATRIX.md).

## 7. HMI (MTP1000 Unified Comfort)

| Screen | Content |
|---|---|
| Overview | Zone tiles (12 today, up to 16) in the farm's layout (state colour, hand badge, moisture), tank, pumps, mains, link/fallback status, alarm banner |
| Zone | State, timer, flow, pressure, panel mode; Start (duration) / Stop through the **same handshake** as the app |
| Pumps & water | Both pumps (run, fault, panel mode, kW, A, hours), well level, filter ΔP, tank |
| Alarms | Unified alarm view with Arabic and English texts from the app's catalog |
| Schedule | Today's fallback runs (read-only) and when they were loaded |
| Settings | Zone config (`DB_Config`): admin only, with HMI user login |

- **Owner decisions (2026-11-24):**
  - Style: **match the app**: the same dark theme and zone state colours, Arabic RTL by default with an EN switch.
  - Overview: **layout A, the zone grid**. A 4 x 3 grid of zone tiles (name, state, timer, flow, hand badge) with a status column beside it (tank, both pumps, pressure and flow, mains). Alarm count, link state, clock and the AR | EN switch sit in the top bar. A bottom bar switches screens: Overview, Zones, Pumps, Alarms, Schedule, Settings.
  - Panel: 1280 x 800 (MTP1000).
- **Build guide:** [HMI_BUILD_GUIDE.md](HMI_BUILD_GUIDE.md). WinCC Unified Openness is not installed, so the owner builds the screens in TIA from that spec. The panel `FarmHMI` is in the project.
- A language button switches Arabic ⇄ English; the colours match the app.
- HMI commands go through `DB_Cmd`, so the PLC checks them exactly as it checks the app's.

## 8. Test plan (PLCSIM Advanced)

1. Hardware and blocks compile with no errors.
2. Download to a PLCSIM Advanced instance on the PC's virtual network.
3. Plant model: our Python simulator plays the farm against the PLC (§9).
4. The app connects with `CONTROLLER_ADAPTER=opcua`, then again with `modbus`. The same checks run for both:
   - start, stop and stop all;
   - a refused start for each reason code;
   - the no-ack path;
   - a panel switch ON/OFF;
   - a power cut under and over 30 min;
   - a link loss over 120 s, where the fallback runs a zone and the app records it when it returns;
   - well dry run;
   - unexpected flow.
5. HMI in the Unified runtime simulator: the same start and stop, in Arabic and in English.
6. Results go into a test record in `docs/`, as in the scenario suite.

## 9. Farm simulation for PLCSIM (owner: reuse the Python simulator)
PLCSIM Advanced has a .NET API (`Siemens.Simatic.Simulation.Runtime.Api`) that reads and writes a virtual CPU's inputs and outputs. A new **plant bridge** mode joins the existing physics engine to it:
- **Every cycle:** read the PLC's outputs (pump starts, wired valves) and the radio-box commands; step the physics; write the inputs (run/fault feedback, analogs as 4–20 mA raw values, mains OK, panel switches).
- **Faults:** the Simulator page's faults (pump trip, well low, power cut, valve stuck…) act on the physics as they do today, so the PLC sees them as real input changes.
- **The app:** it then talks to the **PLC** (OPC UA or Modbus), not to the simulator. That is the real setup.

Built as a small C# bridge (`tools/plcsim/PlcsimBridge.cs`, no new Python package) and a farm model in `apps/simulator/src/plcsim_plant.py`. Run it with `run.bat demo plcsim`.

The panel switches are simulated the same way: the Simulator page sets the two input bits per zone or pump.

## 10. Order of work

1. Create the TIA project (the CPU and modules above; the owner sets the configuration-protection password), plus a PLCSIM Advanced instance.
2. UDTs and DBs, `FB_Link` with the handshake, `FB_ModbusMap`, and the OPC UA server. Connect the app (read-only, then commands).
3. `FB_Zone`, `FB_Pump`, `FB_Hydraulics`, `FB_Interlocks` and the plant model. Run the scenario checks.
4. G7 rules: panel switches, power cut, fallback, dry run, unexpected flow. Adapter work: heartbeat and schedule download.
5. HMI screens.
6. Full test plan, project archive and docs.
