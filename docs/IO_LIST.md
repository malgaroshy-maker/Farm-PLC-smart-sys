# IO_LIST.md

## 1. Purpose

This file defines a PLC-friendly logical I/O model and normalized tags for the simulator and backend.

Final physical addresses will be assigned during hardware engineering.

## 2. Digital Inputs (Suggested)

### System
- DI_SYS_ESTOP
- DI_SYS_PANEL_AUTO
- DI_SYS_PANEL_MANUAL
- DI_SYS_PANEL_MAINT

### Pumps
- DI_WELL_PUMP_RUN_FB
- DI_WELL_PUMP_FAULT
- DI_BOOSTER_PUMP_RUN_FB
- DI_BOOSTER_PUMP_FAULT

### Valves (per zone)
- DI_ZONE_<CODE>_VALVE_OPEN_FB
- DI_ZONE_<CODE>_VALVE_CLOSE_FB

### Communications / Utilities
- DI_SMS_GATEWAY_OK optional
- DI_ROUTER_OK optional
- DI_CONTROL_POWER_OK optional

## 3. Digital Outputs (Suggested)

### Pumps
- DO_WELL_PUMP_START
- DO_BOOSTER_PUMP_START

### Valves
- DO_ZONE_<CODE>_VALVE_OPEN
- DO_ZONE_<CODE>_VALVE_CLOSE

### Indicators
- DO_ALARM_HORN optional
- DO_ALARM_BEACON_RED optional
- DO_ALARM_BEACON_YELLOW optional

## 4. Analog Inputs (Suggested)

- AI_TANK_LEVEL_PCT
- AI_MAIN_PRESSURE_BAR
- AI_MAIN_FLOW_M3H

### Per zone
- AI_ZONE_<CODE>_MOISTURE_PCT

### Future
- AI_WELL_LEVEL
- AI_ZONE_<CODE>_PRESSURE_BAR
- AI_ZONE_<CODE>_FLOW_M3H
- AI_POWER_KW_MAIN

## 5. Internal PLC Tags

### System
- sys.mode.auto
- sys.mode.manual
- sys.mode.maintenance
- sys.online.backend
- sys.online.sms
- sys.estop_active

### Sources
- src.tank.available
- src.tank.level_pct
- src.tank.low_warn
- src.tank.low_crit
- src.well.available
- src.well.dry_run_risk

### Pumps
- pump.well.cmd_start
- pump.well.run_fb
- pump.well.fault
- pump.well.failed_start
- pump.well.runtime_sec

- pump.booster.cmd_start
- pump.booster.run_fb
- pump.booster.fault
- pump.booster.failed_start
- pump.booster.runtime_sec

### Mainline
- main.pressure.bar
- main.flow.m3h

### Per zone
- zone[n].id
- zone[n].enabled
- zone[n].cmd_run
- zone[n].requested_mode
- zone[n].state
- zone[n].active
- zone[n].source_mode
- zone[n].valve_open_cmd
- zone[n].valve_close_cmd
- zone[n].valve_open_fb
- zone[n].runtime_sec
- zone[n].runtime_limit_sec
- zone[n].moisture_pct
- zone[n].health
- zone[n].alarm_count

## 6. Signal Quality Expectations

- all analog tags must carry engineering units
- all state tags must include timestamp in backend state model
- simulator should publish normalized values matching the same schema

## 7. Minimal Instrumentation Set for Phase 1

- 2 pump run/fault feedback groups
- one mainline pressure AI
- one mainline flow AI
- one tank level AI
- one moisture AI per zone
- one logical valve control per zone
