# PRD.md

## 1. Project Identity

**Project Name:** Algaroshy Farm Smart Automated Irrigation System  
**Farm Name:** Algaroshy Farm  
**Originator:** Mahamed Algaroshy — محمد عادل الجروشي

## 2. Product Vision

Build a smart irrigation system for Algaroshy Farm that replaces manual monitoring and manual valve operation with a PLC-driven, sensor-backed, remotely observable and controllable platform.

The system must let owners and authorized operators:

- see the farm on a top-down map
- know in real time which zones are being irrigated
- know whether pressure, flow, and moisture are healthy
- start, stop, and schedule irrigation remotely
- receive alarms for no-flow, low pressure, leaks, low tank level, pump faults, and communication problems
- review history, water usage, runtime, and alarm logs
- keep irrigation running locally even if internet fails

## 3. Problem Statement

The current farm irrigation process depends heavily on manual observation and manual operation. That causes:

- dependence on staff presence
- delayed detection of irrigation problems
- lack of proof that water actually reached the intended field
- no central historical record
- limited remote visibility
- higher risk of overwatering, underwatering, leakage, and wasted pump runtime

## 4. Core Outcome

The finished product should function as a local industrial control system with digital supervision, not only as a remote switching app.

That means:

- PLC handles local logic and safety
- sensors validate irrigation performance
- apps provide monitoring, control, schedules, alarms, and reports
- backend stores telemetry and event history
- simulation mode exists before hardware commissioning

## 5. Farm Context

Known farm characteristics:

- multiple fields with crop groupings including olives, pomegranate, grapes, and mixed fruit trees
- drip irrigation
- well + tank + booster pump arrangement
- some close/lower fields may sometimes be fed directly from well
- electricity is available
- internet is unstable
- current valves are manual
- desired visualization is a top-down map with animated pipelines

## 6. Users and Roles

### 6.1 Owner / Admin
Can:
- view all data
- manage users
- edit schedules
- start/stop zones
- force manual override when permitted
- acknowledge and reset alarms
- configure thresholds and zone rules

### 6.2 Operator
Can:
- view live farm map
- start/stop allowed zones
- execute approved manual operations
- acknowledge selected alarms
- inspect events and reports

### 6.3 Viewer
Can:
- monitor live state
- view reports and history
- view alarms
- cannot issue control commands

## 7. Product Scope

### 7.1 In Scope for First Real Product
- PLC-based pump and valve control
- local autonomous schedules
- field-level zone control
- sensor-backed irrigation validation
- web dashboard
- Android app
- map visualization with animated flow
- alarms, notifications, and history
- reports for irrigation, water usage, pump runtime, and faults
- offline/local-first operation

### 7.2 Out of Scope for Initial Build
- exact agronomic optimization by crop science model
- CCTV analytics
- fertilizer dosing automation
- yield analytics
- tree-level irrigation control
- solar/generator automatic dispatch
- machine-learning prediction

These may come later.

## 8. Functional Requirements

### 8.1 Zone Control
The system shall:

- represent the farm as control zones at field level
- allow one zone at a time by default
- support two zones at a time only when hydraulically allowed
- support per-zone schedules
- support manual start/stop
- support max runtime limits
- support seasonal duration multipliers
- support future subdivision into sub-zones

### 8.2 Water Source Logic
The system shall support:

- tank-fed irrigation via booster pump
- direct well irrigation for selected allowed zones
- configurable source preference by zone
- fallback or failover logic where allowed
- emergency limited watering if tank is low but policy allows it

### 8.3 Pump Control
The system shall control and monitor:

- well pump
- booster pump

The system shall know:
- command state
- run feedback
- fault state
- runtime accumulation
- failed start condition

### 8.4 Valve Control
The system shall:

- replace manual valves with actuated valves
- open and close valves per sequence logic
- detect valve not-open or not-close failures when feedback exists
- support derived fault detection if direct feedback does not exist initially

### 8.5 Monitoring
The system shall display in real time:

- farm zone state
- active irrigation paths
- pressure
- flow
- tank level
- soil moisture
- pump status
- source selection
- active alarms
- comms/online status

### 8.6 Scheduling
The system shall support:

- daily schedules
- weekly schedules
- seasonal programs
- manual immediate run
- pause and stop
- priority and conflict checking
- validation of illegal overlaps

### 8.7 Alarms
The system shall detect:

- no flow
- low pressure
- high pressure
- abnormal high flow / suspected leak
- tank low and critically low
- dry-run risk
- pump trip / failed start
- valve failed movement
- moisture sensor fault
- communication loss
- stale data
- invalid configuration
- hydraulic over-capacity requests

### 8.8 Notifications
The system shall notify via:

- in-app alerts
- web dashboard alerts
- email
- SMS fallback for critical alarms

### 8.9 Reports
The system shall support:

- daily irrigation log
- water usage by zone
- pump runtime
- alarm history
- operator action audit
- selected telemetry trend charts

## 9. Non-Functional Requirements

### 9.1 Reliability
- local control must continue without internet
- telemetry buffer must survive communication outages
- state after restart must be deterministic and safe

### 9.2 Safety
- critical faults must stop unsafe operation locally
- pumps must be protected from dry-run and invalid starts
- dual-zone mode must be blocked if thresholds are not met

### 9.3 Performance
- live state update target: under 2 seconds on local network
- control command response target: under 2 seconds
- map rendering should remain usable on phone and browser

### 9.4 Security
- role-based access control
- audit log for control actions
- secure remote sessions
- clear ownership of admin-only settings

### 9.5 Maintainability
- modular architecture
- explicit schemas
- simulator support
- clean separation of PLC, backend, and UI responsibilities

## 10. Assumptions to Use Until Field Data Is Finalized

- one logical control valve per zone in phase 1 unless engineering says otherwise
- one soil moisture sensor per zone
- one mainline pressure sensor and one mainline flow meter minimum
- dual-zone mode is disabled by default and unlocked only after commissioning
- local data persists first, cloud sync second
- Arabic-first bilingual UI

## 11. Acceptance Criteria

The first working version is successful when it can:

1. run in simulation with realistic farm zones and pump/valve behavior
2. execute schedules locally without internet dependency
3. show live zone status on web and Android
4. display animated map flow for active irrigation paths
5. detect and display key alarms
6. log irrigation events and telemetry
7. enforce user roles
8. export core reports
9. support manual remote start/stop subject to interlocks
10. recover to a safe state after restart

## 12. Deliverables Required for Vibecoding

This PRD depends on the rest of the pack:

- `ARCHITECTURE.md`
- `DOMAIN_MODEL.md`
- `DATABASE_SCHEMA.md`
- `API.md`
- `REALTIME_EVENTS.md`
- `IO_LIST.md`
- `PLC_CONTROL_LOGIC.md`
- `ALARM_MATRIX.md`
- `UI_WIREFRAMES.md`
- `SIMULATION_PLAN.md`
- `IMPLEMENTATION_PLAN.md`
- `TEST_PLAN.md`
- `AI_AGENT_RUNBOOK.md`
