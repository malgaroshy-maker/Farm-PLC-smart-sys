# PLC tags (I/O)

Create this tag table, **Farm_IO**, in TIA Portal before generating the blocks from the sources. The addresses are proposals for the module order in [docs/PLC_PROGRAM.md](../docs/PLC_PROGRAM.md) §2; change them to whatever the hardware configuration assigns.

| Tag | Type | Address | Meaning |
|---|---|---|---|
| "DI_EStopOk" | Bool | %I0.0 | E-stop circuit healthy (NC contact; FALSE = pressed) |
| "DI_MainsOk" | Bool | %I0.1 | Mains present (relay before the UPS) |
| "DI_BoosterRun" | Bool | %I0.2 | Booster pump running (contactor aux / drive run) |
| "DI_BoosterFault" | Bool | %I0.3 | Booster overload / drive fault |
| "DI_WellRun" | Bool | %I0.4 | Well pump running |
| "DI_WellFault" | Bool | %I0.5 | Well pump overload / drive fault |
| "DI_BoosterHand" | Bool | %I0.6 | Booster selector in HAND |
| "DI_BoosterOff" | Bool | %I0.7 | Booster selector in OFF |
| "DI_WellHand" | Bool | %I1.0 | Well selector in HAND |
| "DI_WellOff" | Bool | %I1.1 | Well selector in OFF |
| "DI_ZoneOnLo" | Byte | %IB2 | Zone selectors 1–8 in ON (bit 0 = zone 1) |
| "DI_ZoneOnHi" | Byte | %IB3 | Zone selectors 9–16 in ON |
| "DI_ZoneOffLo" | Byte | %IB4 | Zone selectors 1–8 in OFF |
| "DI_ZoneOffHi" | Byte | %IB5 | Zone selectors 9–16 in OFF |
| "AI_TankLevel" | Int | %IW6 | Tank level, 4–20 mA |
| "AI_MainPressure" | Int | %IW8 | Mainline pressure, 4–20 mA |
| "AI_MainFlow" | Int | %IW10 | Mainline flow, 4–20 mA |
| "AI_WellLevel" | Int | %IW12 | Well water level, 4–20 mA |
| "AI_FilterDp" | Int | %IW14 | Filter pressure drop, 4–20 mA |
| "DQ_ValveLo" | Byte | %QB0 | Wired zone valves 1–8 (bit 0 = zone 1) |
| "DQ_ValveHi" | Byte | %QB1 | Wired zone valves 9–16 |
| "DQ_BoosterStart" | Bool | %Q2.0 | Booster start |
| "DQ_WellStart" | Bool | %Q2.1 | Well pump start |
| "DQ_Beacon" | Bool | %Q2.2 | Red alarm beacon |
| "DQ_Horn" | Bool | %Q2.3 | Horn (logic decided at commissioning) |

System constants the code uses (their names come from the hardware configuration; rename in the code if TIA names them differently):
- `"Local~PROFINET_interface_1"`: the CPU's PROFINET interface, for the Modbus TCP server (`FB_ModbusMap`).
- `"Local~CM_PtP_1"`: the RS-485 module, for the radio boxes and the energy meters (`FB_RadioBoxes`).
