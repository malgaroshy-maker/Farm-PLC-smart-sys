# Field trial: one zone on the real farm

Everything so far was tested in simulation. This trial puts **one zone** on real hardware. Do the steps in order and
stop at the first one that fails. A person stays beside the main valve and the pump isolator for every wet test.

Zone: ______________  Date: ______________  Electrician: ______________  Owner present: ______________

## 1. Before any wiring
- [ ] The hardware list is bought and checked against `HARDWARE_BOM_DRAFT.md` and `IO_LIST.md`.
- [ ] A qualified electrician designs and checks the pump panel: isolator, overload and dry-run protection,
      earth leakage protection, surge protection, emergency stop that cuts the pump **without** the PLC.
- [ ] Every zone and pump has a Hand-Off-Auto switch that works with the PLC switched off.
- [ ] The valve fails **closed** when power is lost. Tested by hand.
- [ ] The soil-moisture levels stay "not confirmed" during the trial, so soil never starts or stops water by itself.

## 2. Dry checks (no water, pump isolated)
- [ ] Each input is seen in the PLC: switch positions, emergency stop, power-good, tank level, flow, pressure,
      pump running feedback.
- [ ] Each output moves the right device only: the trial zone's valve, then the pump contactor (motor disconnected).
- [ ] A broken sensor wire is shown as a sensor fault, and the PLC stops what depends on it.
- [ ] The PLC clock matches the phone's clock after the app connects.
- [ ] The panel buttons work: Start, Stop, Stop all. Panel users and rights are set (`HMI_BUILD_GUIDE.md`).

## 3. Measure the real numbers (first water, pump run by hand)
Run the trial zone for 10 minutes three times, on different days if possible. Write down the steady values.

| Run | Flow (m³/h) | Pressure at zone (bar) | Pump current (A) | Filter pressure difference (bar) | Seconds until flow is steady |
|---|---|---|---|---|---|
| 1 |  |  |  |  |  |
| 2 |  |  |  |  |  |
| 3 |  |  |  |  |  |

- [ ] The flow meter agrees with a bucket or tank-level measurement within 10 %.
- [ ] Walk the line during the run: no leaks, no blocked section, every tree row gets water.

## 4. Limits the owner approves
The PLC's present flow limits (2 to 6 m³/h) are **bench values for the simulator**. Replace them with limits from the
measured runs. Nothing runs unattended before the owner signs this table.

| Limit | Measured basis | Approved value |
|---|---|---|
| Lowest normal flow (below it: no-flow fault) |  |  |
| Highest normal flow (above it: leak fault) |  |  |
| Time allowed for flow to appear |  |  |
| Longest run |  |  |
| Tank "low" and "critical" levels |  |  |

Owner's signature: ______________  Date: ______________

- [ ] Limits entered in the app and written to the PLC, then read back from the PLC and compared (`../plc/README.md`).

## 5. Safety tests with water (one at a time)
| Test | How | Expected | Pass |
|---|---|---|---|
| Stop all from the phone | Press during a run | Pump stops, then the valve closes | ☐ |
| Stop all on the panel | Same | Same, and the app's program ends | ☐ |
| Emergency stop | Press during a run | Every pump stops at once; nothing restarts by itself | ☐ |
| No flow | Close the zone's manual valve | The run stops with a no-flow alarm | ☐ |
| Leak | Open a drain after the flow meter | The run stops with a leak alarm | ☐ |
| Power cut | Switch off the supply, then restore it | Nothing starts by itself before the rules allow it; the cut is recorded | ☐ |
| Zone switch left ON | Restore power with a switch ON | No start until the switch was moved off and on again | ☐ |
| Empty tank | Lower the level signal below critical | Booster pump locked out | ☐ |
| App or internet lost | Unplug the farm PC's network | The phone shows "no connection"; the panel works; the stored schedule follows its rules | ☐ |
| Sensor fault | Disconnect the tank level sensor | No refill and a sensor fault | ☐ |

## 6. Watched operation
- [ ] One week of runs started by a person who stays at the farm.
- [ ] One week of scheduled runs with a person at the farm.
- [ ] Every alarm in those two weeks is understood and written down.
- [ ] Alerts reach the owner's phone (Telegram or push).
- [ ] A backup is made and restored once on the farm PC.

Only after all of this does a second zone get connected, with its own measured limits.
