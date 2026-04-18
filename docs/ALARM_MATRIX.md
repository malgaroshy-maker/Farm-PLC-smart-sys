# ALGAROSHY FARM — ALARM_MATRIX.md

**Project:** Algaroshy Farm Smart Automated Irrigation System  
**Farm Name:** Algaroshy Farm  
**Originator:** Mahamed Algaroshy — محمد عادل الجروشي  
**Document Type:** Alarm Matrix / PLC-Backend-App-Notification Behavior  
**Purpose:** Define alarms, severities, trigger logic, PLC actions, backend actions, operator guidance, app behavior, acknowledgements, reset rules, and logging requirements so the project can be vibecoded consistently across PLC simulation, backend services, web app, and Android app.

---

## 1. Document Goals

This alarm matrix is intended to make the project implementable by coding agents and engineering teams with minimal ambiguity.

It defines:

- what conditions create alarms
- alarm severity and category
- what the PLC should do immediately
- what the backend should do
- what the UI should display
- what notifications should be sent
- whether acknowledgement is required
- whether manual reset is required
- what data must be logged
- what operator guidance should be shown

This document should be treated as the source of truth for:

- PLC fault logic
- backend alarm engine behavior
- mobile/web alarm center UI
- notification routing rules
- simulation scenarios
- acceptance testing

---

## 2. Alarm Design Principles

1. **Local safety first**  
   The PLC must react locally to critical process and equipment faults even if the internet or backend is unavailable.

2. **Separation of responsibilities**
   - **PLC**: immediate protection, interlocks, equipment stop/start decisions
   - **Backend**: aggregation, notification, history, trends, correlation
   - **Web/Android**: visualization, acknowledgement, operator action, guided recovery

3. **Alarm quality over quantity**  
   Avoid alarm flooding. Use:
   - debounce timers
   - suppression where appropriate
   - state-based enable logic
   - escalation only when needed

4. **Context-aware alarms**  
   Alarm conditions should be evaluated only when relevant.  
   Example: `NO_FLOW` should not alarm when no zone is expected to run.

5. **Critical alarms must be unmistakable**  
   Critical pump-protection, dry-run, and severe pressure conditions must cause strong UI indication and immediate protective PLC action.

6. **Notifications must degrade gracefully**
   - push / web first if online
   - email if configured
   - SMS fallback for critical alarms when internet is lost but GSM is available

7. **Every alarm must be testable**
   Each alarm should have:
   - a simulation method
   - acceptance criteria
   - expected operator guidance

---

## 3. Severity Model

### Severity Levels

| Code | Severity | Meaning | Typical Behavior |
|---|---|---|---|
| S0 | Info | Informational event, not a fault | Log only, optional UI event |
| S1 | Warning | Abnormal but not yet critical | Show warning, notify as configured |
| S2 | Major | Process failure or significant equipment issue | Stop affected zone or subsystem, notify strongly |
| S3 | Critical | Safety/equipment protection required | Immediate PLC action, persistent alarm, strong notifications |

### Suggested UI Color Mapping

| Severity | Color |
|---|---|
| Info | Blue / Neutral |
| Warning | Yellow |
| Major | Orange |
| Critical | Red |

---

## 4. Alarm Categories

- **Process**: flow, pressure, irrigation performance, cycle problems
- **Equipment**: pump fault, valve fault, actuator fault, sensor fault
- **Utility**: power, generator future integration, communication
- **Water Source**: tank low, dry-run risk, well source unavailable
- **Configuration / Data**: invalid schedule, conflicting zone request, missing thresholds
- **Security / Access**: unauthorized command attempts, role violations
- **Maintenance**: service due, recurring unstable sensor, repeated retries

---

## 5. Alarm State Model

Each alarm instance should use this lifecycle:

1. **Normal**
2. **Pending** (condition detected, debounce running)
3. **Active / Unacknowledged**
4. **Active / Acknowledged**
5. **Returned to Normal / Latched History**
6. **Reset** (if manual reset required)

### Alarm Fields

Each alarm record should include at least:

- `alarm_code`
- `alarm_name`
- `severity`
- `category`
- `status` (`active_unacked`, `active_acked`, `cleared`, `suppressed`)
- `zone_id` (nullable)
- `device_id` (nullable)
- `trigger_timestamp`
- `clear_timestamp`
- `ack_timestamp`
- `ack_user_id`
- `reset_timestamp`
- `reset_user_id`
- `current_value`
- `threshold_value`
- `source_layer` (`plc`, `backend`, `derived`)
- `correlation_key`
- `operator_message_ar`
- `operator_message_en`
- `recommended_action_ar`
- `recommended_action_en`

---

## 6. Debounce, Persistence, and Suppression Rules

### 6.1 Debounce
Suggested default debounce timers:

- pressure transient warning: 5–10 sec
- no flow warning: 10–20 sec after command to run
- valve failed to move: 5–15 sec after command
- communication heartbeat loss: 30–120 sec depending on component
- moisture abnormal trend: evaluated over minutes/hours, not seconds

### 6.2 Persistence
Some alarms should be latched until acknowledged or manually reset, even if the process condition clears briefly.

Examples:
- dry-run risk
- booster pump fault
- well pump fault
- critical sensor failure on active system
- repeated no-flow after retry

### 6.3 Suppression
Examples:
- suppress `NO_FLOW` if no zone is commanded on
- suppress `VALVE_NOT_OPEN` if the zone start sequence was aborted before valve command
- suppress communication alarms during maintenance mode if explicitly configured
- suppress duplicate downstream alarms if a parent critical alarm already explains the root cause

---

## 7. Notification Routing Model

### 7.1 Channels
- in-app push
- web live alert center
- email
- SMS fallback

### 7.2 Default Routing by Severity

| Severity | In-App | Web | Email | SMS |
|---|---|---|---|---|
| S0 Info | Optional | Yes | No | No |
| S1 Warning | Yes | Yes | Optional digest | No |
| S2 Major | Yes | Yes | Yes | Optional |
| S3 Critical | Yes | Yes | Yes | Yes |

### 7.3 Escalation
If a critical alarm remains active and unacknowledged beyond configured time:
- resend push
- resend SMS to escalation list
- optionally notify secondary owners/admins

Suggested escalation times:
- S2 Major: 10–15 min
- S3 Critical: 2–5 min

---

## 8. PLC Response Strategy by Alarm Type

### Immediate stop required
Used when continuing operation may damage equipment or produce invalid irrigation:
- dry-run risk
- severe low tank level
- booster pump fault
- severe overpressure
- emergency stop activated

### Stop affected zone only
Used when issue is local to a zone:
- zone valve failed to open
- zone valve failed to close
- no flow for specific zone if per-zone diagnosis is supported
- local pressure anomaly associated with one branch

### Retry once then alarm
Used for potentially transient process issues:
- zone start no-flow
- valve motion timeout
- temporary low pressure during start

### Continue locally, alarm only
Used when system operation can safely continue:
- cloud sync loss
- internet loss
- report export failure
- non-critical sensor trend anomaly

---

## 9. Master Alarm Matrix

> Thresholds are placeholders and must be tuned during commissioning and hydraulic testing.

| Alarm Code | Alarm Name | Category | Severity | Typical Trigger | PLC Immediate Action | Backend Action | Notification | Ack Req | Manual Reset | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| ALM-001 | Tank Low Level Warning | Water Source | S1 | Tank level below warning threshold | Allow operation based on config | Log, show warning, monitor trend | In-app, web | No | No | Can escalate if active too long |
| ALM-002 | Tank Critically Low Level | Water Source | S3 | Tank level below critical threshold | Stop booster / block new irrigation except allowed emergency logic | Mark source unavailable, notify strongly | Push, web, email, SMS | Yes | Optional | Emergency watering logic may permit restricted zones only |
| ALM-003 | Tank Level Sensor Fault | Equipment | S2 | Invalid / missing tank sensor signal | Use fallback if safe, otherwise block affected logic | Flag sensor degraded | Push, web, email | Yes | Yes | Must define fallback policy |
| ALM-004 | Well Pump Fault / Trip | Equipment | S3 | Pump overload / thermal trip / feedback fault | Stop well pump and dependent sequences | Raise critical source alarm | Push, web, email, SMS | Yes | Yes | Latching |
| ALM-005 | Booster Pump Fault / Trip | Equipment | S3 | Booster fault feedback active | Stop booster and all dependent irrigation | Mark irrigation unavailable | Push, web, email, SMS | Yes | Yes | Latching |
| ALM-006 | Booster Pump Failed to Start | Equipment | S2 | Start command but run feedback absent after timeout | Stop sequence, block dependent valves | Log failed start attempt | Push, web, email | Yes | Yes | Retry once may be allowed |
| ALM-007 | Well Pump Failed to Start | Equipment | S2 | Start command but run feedback absent after timeout | Abort fill/source sequence | Log failed start attempt | Push, web, email | Yes | Yes | Retry once optional |
| ALM-008 | Mainline Low Pressure Warning | Process | S1 | Pressure below warning threshold for debounce period | Continue or restrict based on config | Log trend, correlate with active zones | Push, web | No | No | Often first sign of blockage / source issue |
| ALM-009 | Mainline Critically Low Pressure | Process | S2/S3 | Pressure below critical threshold while irrigation expected | Stop affected zones or all depending on scope | Create process incident | Push, web, email, SMS if critical | Yes | Optional | Criticality depends on source/zone design |
| ALM-010 | Mainline High Pressure Warning | Process | S1 | Pressure above warning threshold | Continue with caution or reduce operations | Log trend | Push, web | No | No | Check closed valves / blockage |
| ALM-011 | Mainline Critically High Pressure | Process | S3 | Pressure above critical threshold | Stop booster and isolate if possible | Raise critical pressure event | Push, web, email, SMS | Yes | Yes | Equipment protection |
| ALM-012 | No Flow Detected | Process | S2 | Zone/pump commanded on, main flow below expected after delay | Retry or stop affected sequence | Correlate with valve/pump source state | Push, web, email | Yes | Optional | Root cause may be valve or source |
| ALM-013 | Abnormal High Flow / Leak Suspected | Process | S2 | Flow above expected max band for current zone combination | Stop affected operation or full irrigation depending on severity | Log suspected leak event | Push, web, email, optional SMS | Yes | Optional | Useful for pipe break detection |
| ALM-014 | Flow Meter Sensor Fault | Equipment | S2 | Flow signal invalid, frozen, or out of range | Continue only if safe policy allows | Mark diagnostics degraded | Push, web, email | Yes | Yes | Some logic may be disabled |
| ALM-015 | Pressure Sensor Fault | Equipment | S2 | Pressure signal invalid / frozen | Continue only if safe fallback exists | Flag critical instrumentation degradation | Push, web, email | Yes | Yes | Safety logic may block dual-zone mode |
| ALM-016 | Soil Moisture Sensor Fault | Equipment | S1/S2 | Sensor invalid / offline | Ignore moisture-based logic for that zone | Mark zone as schedule-only | Push, web | Optional | Yes | Not always process-critical |
| ALM-017 | Soil Moisture Too Low After Cycle | Process | S1/S2 | Moisture remains below expected band after irrigation cycle | Do not stop operation immediately | Create advisory / investigation event | Push, web, optional email | No | No | Check clogged emitters or duration |
| ALM-018 | Soil Moisture Too High / Overwatering Risk | Process | S1 | Moisture above target high band | Suggest shorter future duration | Log agronomic advisory | Push, web | No | No | Mostly analytics/optimization |
| ALM-019 | Valve Failed to Open | Equipment | S2 | Open command issued, but no open feedback / derived success absent | Stop affected zone start | Correlate with no-flow | Push, web, email | Yes | Optional | Retry once may be allowed |
| ALM-020 | Valve Failed to Close | Equipment | S2/S3 | Close command issued, but valve remains open | Stop pump if necessary, isolate if possible | Raise persistent irrigation risk | Push, web, email, SMS if water loss risk high | Yes | Yes | Important for drip losses |
| ALM-021 | Unexpected Valve State Change | Equipment | S2 | Valve feedback changes without command | Re-evaluate sequence, possibly stop | Log integrity/security concern | Push, web, email | Yes | Yes | Could indicate wiring or actuator fault |
| ALM-022 | Zone Runtime Exceeded | Process | S1/S2 | Zone remains active longer than configured max runtime | Stop affected zone or request confirmation | Log schedule deviation | Push, web, email optional | Yes | Optional | Prevent accidental continuous watering |
| ALM-023 | Zone Start Conflict | Configuration | S1 | Requested zone combination not allowed | Block command | Log rejected request | Web/in-app | No | No | Not a process fault |
| ALM-024 | Hydraulic Capacity Exceeded | Configuration/Process | S2 | Requested zone combination exceeds allowed pressure/flow capacity | Block or stop second zone | Log capacity violation | Push, web, email | Yes | No | Important for dual-zone logic |
| ALM-025 | Invalid Schedule Configuration | Configuration | S1 | Schedule overlaps illegally / missing source / invalid duration | Do not execute invalid schedule | Mark schedule invalid | Web, in-app, optional email | No | No | Admin correction required |
| ALM-026 | Irrigation Cycle Aborted | Process | S1/S2 | Sequence aborted due to fault or manual stop | Stop relevant equipment safely | Log cycle outcome | Web, in-app | No | No | Classification depends on cause |
| ALM-027 | Dry-Run Risk | Water Source | S3 | Well level / pump current / source logic indicates dry-run risk | Stop affected pump immediately | Raise critical source protection alarm | Push, web, email, SMS | Yes | Yes | One of the most important alarms |
| ALM-028 | Source Unavailable | Water Source | S2 | Selected source cannot be used | Block relevant zones or switch source | Attempt source failover if configured | Push, web, email | Yes | Optional | Important for direct-well vs tank logic |
| ALM-029 | Communication Lost — PLC to Backend | Utility | S1/S2 | Backend heartbeat missing from PLC/edge | Continue local PLC operation | Mark stale data state | Web banner, push to admins | Optional | No | Local automation continues |
| ALM-030 | Communication Lost — Backend to App Push | Utility | S1 | Notification provider unavailable | No PLC effect | Queue/retry notifications | Web, admin log | No | No | Should not affect process |
| ALM-031 | Internet / Cloud Sync Lost | Utility | S1 | WAN unavailable or cloud sync failing | Continue locally | Buffer data for later sync | Web, in-app, optional email | No | No | SMS still possible with GSM |
| ALM-032 | GSM / SMS Gateway Fault | Utility | S1/S2 | SMS module unavailable | Continue locally | Mark degraded alerting path | Web, in-app, email | Optional | Yes | Important when internet is unstable |
| ALM-033 | Power Loss / Control Power Failure | Utility | S3 | Control power lost / UPS absent / restart event | Equipment de-energizes safely by design | Log restart incident after recovery | Push/email/SMS after recovery if possible | Yes | Yes | Requires restart recovery behavior |
| ALM-034 | PLC Restart / Warm Start Event | Utility | S0/S1 | PLC rebooted / restarted | Execute safe startup logic | Log event and pre-restart context if possible | Web, optional push | No | No | Important for audit trail |
| ALM-035 | Unauthorized Command Attempt | Security | S1/S2 | User without permission attempts control command | Reject command | Log security event | Web, in-app, optional email | No | No | Repeated events can escalate |
| ALM-036 | Repeated Fault on Same Zone | Maintenance | S1/S2 | Same zone triggers same fault repeatedly in window | Continue normal protection behavior | Open maintenance advisory | Push, web, email optional | No | No | Good for maintenance planning |
| ALM-037 | Sensor Drift Suspected | Maintenance | S1 | Sensor deviates persistently from expected correlations | No PLC action | Create diagnostic advisory | Web, in-app | No | No | Trend-based |
| ALM-038 | Maintenance Due — Pump | Maintenance | S0/S1 | Runtime/service interval exceeded | No direct stop unless configured | Create maintenance task | Web, email optional | No | No | Future expansion |
| ALM-039 | Maintenance Due — Filters / Valves | Maintenance | S0/S1 | Service interval reached | No direct stop | Create maintenance task | Web, email optional | No | No | Future expansion |
| ALM-040 | Camera / CCTV Offline | Utility/Future | S1 | Camera heartbeat lost | No PLC action | Mark camera unavailable | Web, in-app | No | No | Future phase |
| ALM-041 | Emergency Stop Activated | Utility/Protection | S3 | Local E-stop input active | Immediate stop of affected equipment | Raise critical local intervention alarm | Push, web, email, SMS | Yes | Yes | Must be latching |
| ALM-042 | Manual Mode Active | Info | S0 | Zone/system in manual mode | No fault action | Display operational state | Web, in-app | No | No | Should appear clearly but not as danger |
| ALM-043 | Maintenance Mode Active | Info | S0 | Maintenance mode enabled | Change logic permissions | Log state change | Web, in-app | No | No | Suppresses selected alarms if configured |
| ALM-044 | Data Stale / Last Good State Only | Utility | S1 | UI data older than freshness threshold | No PLC action | Mark stale badge on UI | Web, in-app | No | No | Important for remote trust |
| ALM-045 | Cloud Backup Failure | Utility | S1 | Backup/archive job failed | No PLC action | Retry backup, log failure | Web, email optional | No | No | Long-term storage issue |
| ALM-046 | Zone Not Watered as Expected | Process | S2 | Derived logic: zone scheduled and completed but validation poor | Flag irrigation quality failure | Raise investigation event | Push, web, email | Yes | No | Uses flow/pressure/moisture correlation |
| ALM-047 | Excessive Start/Stop Cycling | Equipment/Process | S2 | Pumps/valves cycling too frequently in time window | Restrict auto restarts | Log equipment stress event | Push, web, email | Yes | Optional | Protects hardware |
| ALM-048 | Direct-Well Supply Not Permitted | Configuration | S1 | Zone requested on direct-well path but config disallows | Block sequence | Log command rejection | Web, in-app | No | No | Relevant for close/lower fields |
| ALM-049 | Source Switchover Failed | Water Source | S2 | Automatic failover from tank/well did not complete | Abort dependent sequence | Create process interruption event | Push, web, email | Yes | Optional | Important for hybrid source logic |
| ALM-050 | Configuration Missing Thresholds | Configuration | S1 | Zone/device lacks required threshold values | Block related smart decisions | Log config defect | Web, in-app, optional email | No | No | Must be prevented in admin UI |

---

## 10. Operator Guidance Templates

Each alarm should ship with built-in operator guidance in Arabic and English.

### Example Template Structure

- **What happened**
- **Why it matters**
- **Immediate recommended action**
- **Possible causes**
- **Next checks**
- **When to escalate**

### Example: ALM-012 No Flow Detected

**Arabic operator message**  
تم اكتشاف عدم وجود تدفق مياه رغم وجود أمر تشغيل للري.

**Arabic recommended action**  
تحقق من حالة المضخة، وحالة الصمام الخاص بالمنطقة، ومستوى الخزان، وضغط الخط الرئيسي، واحتمال وجود انسداد أو انقطاع في الخط.

**English operator message**  
No water flow was detected even though irrigation was commanded to run.

**English recommended action**  
Check pump status, zone valve position, tank/source availability, mainline pressure, and possible blockage or broken line conditions.

---

## 11. Ack and Reset Rules

### 11.1 Acknowledgement Required
Typically required for:
- S2 Major alarms
- S3 Critical alarms
- repeated or persistent equipment faults

Ack means:
- a user has seen the alarm
- the alarm remains active if the condition remains true
- ack does not equal reset

### 11.2 Manual Reset Required
Typically required for:
- pump trip/fault
- emergency stop
- dry-run protection
- severe overpressure
- latched critical instrumentation faults

Reset should only be possible when:
- the root condition has cleared
- the system state allows reset
- the user has sufficient permission

---

## 12. UI Requirements for Alarm Center

The web and Android apps should include an Alarm Center with:

- active alarms list
- active critical banner
- per-zone alarm filter
- severity filter
- acknowledgement action
- manual reset action where allowed
- alarm details panel
- operator guidance
- related values at trigger time
- event timeline
- notification delivery status
- stale data indicator
- Arabic/English support

### Required columns
- severity icon
- alarm code
- alarm name
- zone/device
- active since
- current status
- current value vs threshold
- acknowledged by
- source layer
- recommended action

---

## 13. Realtime Event Contracts for Vibecoding

The backend should emit real-time alarm events like:

```json
{
  "type": "alarm.active",
  "alarm_code": "ALM-012",
  "severity": "S2",
  "category": "process",
  "status": "active_unacked",
  "zone_id": "zone_rumman_4",
  "device_id": "flow_main_01",
  "message_ar": "تم اكتشاف عدم وجود تدفق مياه رغم وجود أمر تشغيل للري.",
  "message_en": "No water flow was detected while irrigation was expected to run.",
  "current_value": 0.0,
  "threshold_value": 2.5,
  "triggered_at": "2026-04-18T10:15:00Z",
  "source_layer": "plc",
  "requires_ack": true,
  "requires_manual_reset": false
}
```

```json
{
  "type": "alarm.cleared",
  "alarm_code": "ALM-012",
  "status": "cleared",
  "zone_id": "zone_rumman_4",
  "cleared_at": "2026-04-18T10:18:42Z"
}
```

```json
{
  "type": "alarm.acknowledged",
  "alarm_code": "ALM-012",
  "acknowledged_by": "user_001",
  "acknowledged_at": "2026-04-18T10:16:21Z"
}
```

---

## 14. PLC Tag Suggestions for Alarm Implementation

Suggested PLC / backend alarm-oriented tags:

- `sys.alarm_summary.active_count`
- `sys.alarm_summary.critical_count`
- `sys.alarm_summary.major_count`
- `sys.alarm_summary.warning_count`
- `sys.alarm_summary.last_alarm_code`
- `sys.mode.auto`
- `sys.mode.manual`
- `sys.mode.maintenance`
- `sys.comm.backend_online`
- `sys.comm.internet_online`
- `sys.comm.sms_gateway_online`
- `src.tank.level_pct`
- `src.tank.low_warn`
- `src.tank.low_crit`
- `src.well.dry_run_risk`
- `pump.well.run_fb`
- `pump.well.fault`
- `pump.booster.run_fb`
- `pump.booster.fault`
- `main.pressure.bar`
- `main.flow.m3h`
- `zone[n].cmd_run`
- `zone[n].active`
- `zone[n].valve_open_fb`
- `zone[n].flow_expected_min`
- `zone[n].flow_expected_max`
- `zone[n].pressure_expected_min`
- `zone[n].runtime_sec`
- `zone[n].runtime_limit_sec`
- `zone[n].moisture_pct`
- `zone[n].sensor_fault`
- `zone[n].alarm_active_count`

---

## 15. Simulation Scenarios

The simulation prototype should include test scenes for:

1. Tank level drops below warning threshold
2. Tank level drops below critical threshold during irrigation
3. Booster pump start command but no run feedback
4. Well pump trip during fill cycle
5. Valve commanded open but no flow detected
6. High flow spike indicating suspected leak
7. Mainline pressure collapse when attempting dual-zone run
8. Sensor stuck value / communication loss
9. Internet loss while PLC continues irrigation
10. SMS gateway unavailable during critical alarm
11. Repeated fault on same zone across several days
12. Direct-well source unavailable but tank source available
13. Emergency stop activation and manual reset sequence

Each scenario should define:
- preconditions
- fault injection method
- expected PLC action
- expected backend alarm event
- expected UI behavior
- expected notification behavior
- reset method

---

## 16. Acceptance Criteria

This alarm system is acceptable when:

1. Critical equipment-protection alarms trigger locally at the PLC without backend dependency.
2. Alarm severities are reflected consistently in PLC state, backend state, web app, and Android app.
3. Active alarms can be acknowledged and, where required, manually reset.
4. Duplicate and irrelevant alarms are suppressed appropriately.
5. Critical alarms can trigger SMS fallback.
6. Alarm history captures trigger, ack, clear, and reset information.
7. Each major alarm has an operator guidance message in Arabic and English.
8. Simulation scenarios reproduce the expected alarm behavior.
9. Stale data conditions are clearly distinguished from healthy online telemetry.
10. Zone-level and system-level alarms are both visible and filterable.

---

## 17. Implementation Order for Vibecoding Agents

Recommended order:

1. Define shared alarm enums and schemas
2. Build backend alarm model and persistence
3. Add PLC simulation tags and alarm state evaluator
4. Implement notification routing service
5. Implement web alarm center UI
6. Implement Android alarm center UI
7. Add bilingual operator guidance content
8. Add simulation test harness and scripted scenarios
9. Add analytics for recurring faults and maintenance advisories

---

## 18. Suggested Shared Enums

```ts
export type AlarmSeverity = "S0" | "S1" | "S2" | "S3";
export type AlarmCategory =
  | "process"
  | "equipment"
  | "utility"
  | "water_source"
  | "configuration"
  | "security"
  | "maintenance";
export type AlarmStatus =
  | "pending"
  | "active_unacked"
  | "active_acked"
  | "cleared"
  | "suppressed";
```

---

## 19. Related Documents

This file should be used together with:

- `algaroshy_farm_vibecode_prd.md`
- `algaroshy_farm_ARCHITECTURE.md`
- `algaroshy_farm_API.md`
- `algaroshy_farm_IO_LIST.md`

Recommended next file:
- `UI_WIREFRAMES.md`
or
- `PLC_CONTROL_LOGIC.md`

---

## 20. Final Note

Thresholds, timing values, and some source-switching details in this alarm matrix are intentionally preliminary. They should be tuned during site survey, hydraulic validation, pump data review, and commissioning.

However, the structure in this document is detailed enough to let coding agents and developers start implementing:

- shared alarm models
- PLC simulation behavior
- backend alarm persistence
- real-time alarm events
- notification logic
- UI alarm center behavior
- test scenarios

with a strong and consistent design baseline.
