# API.md

## 1. API Style

- REST for CRUD and commands
- WebSocket for real-time updates
- JSON payloads
- role-based authorization
- stable version prefix: `/api/v1`

## 2. Authentication

### POST /api/v1/auth/login
Request:
```json
{ "username": "admin", "password": "secret" }
```

Response:
```json
{
  "access_token": "jwt",
  "user": { "id": "u1", "name": "Mahamed", "role": "owner_admin" }
}
```

### POST /api/v1/auth/logout
Invalidates session if applicable.

## 3. Farm and Config

### GET /api/v1/farm
Returns top-level farm metadata.

### GET /api/v1/zones
List zones with current state summary.

### GET /api/v1/zones/{zoneId}
Returns zone details.

### POST /api/v1/zones
Create zone.

### PATCH /api/v1/zones/{zoneId}
Edit zone config.

### GET /api/v1/zone-combinations
Return allowed dual-zone combinations.

### PUT /api/v1/zone-combinations
Replace or update combination matrix.

## 4. Devices

### GET /api/v1/pumps
### GET /api/v1/valves
### GET /api/v1/sensors
### PATCH /api/v1/pumps/{pumpId}
### PATCH /api/v1/valves/{valveId}
### PATCH /api/v1/sensors/{sensorId}

## 5. Schedules & Programs

Sequential irrigation programs (Milestone D). Each program defines a start time in farm local time (`Africa/Tripoli`), a weekday mask, and an ordered list of zone steps with durations.

### GET /api/v1/schedules
List all irrigation programs with their ordered steps and computed total duration.
Accessible to all authenticated users.

### GET /api/v1/schedules/upcoming?hours=24
Returns scheduled upcoming runs in the next N hours (in farm local time). Feeds dashboard cards.

### POST /api/v1/schedules/check-conflicts
Validates a program against current schedule without persisting. Returns `{ "ok": true }` or `{ "ok": false, "conflict": { "code", "message_en", "message_ar", "details" } }`.

### POST /api/v1/schedules
Create a new program. Admin only. Runs conflict checks before saving; rejects with 409 Conflict if an overlap or hydraulic conflict is found.
```json
{
  "name": "Morning Pomegranate Run",
  "start_time_local": "06:00",
  "weekday_mask": "1,2,3,4,5,6,7",
  "steps": [
    { "zone_id": "zone_rumman_1", "step_order": 1, "duration_min": 30 },
    { "zone_id": "zone_rumman_2", "step_order": 2, "duration_min": 30 }
  ]
}
```

### GET /api/v1/schedules/{programId}
Get single program with steps.

### PATCH /api/v1/schedules/{programId}
Update program details or steps. Admin only. Validates conflicts.

### PATCH /api/v1/schedules/{programId}/toggle
Toggle program enabled / disabled state (`{ "enabled": boolean }`). Accessible to Operator and Admin.

### DELETE /api/v1/schedules/{programId}
Delete a program. Admin only.

## 5b. Irrigation Cycle Log

Tracks execution history for all zone runs (manual, scheduled, scenario).

### GET /api/v1/cycles
Query cycle history with filters:
- `zone_id`: filter by zone
- `program_id`: filter by program
- `outcome`: completed | aborted | faulted | manual_stop | skipped
- `from_date` / `to_date`: ISO timestamps or farm dates
- `page` / `limit`: pagination (default limit 50)

### GET /api/v1/cycles/recent/{zoneId}?limit=5
Returns the most recent N cycles for a given zone. Feeds the zone drawer history.

## 6. Commands

### POST /api/v1/commands/start-zone
```json
{ "zone_id": "zone_grapes_1", "mode": "manual" }
```

### POST /api/v1/commands/stop-zone
```json
{ "zone_id": "zone_grapes_1" }
```

### POST /api/v1/commands/stop-all
```json
{ "reason": "operator_request" }
```

### POST /api/v1/commands/set-mode
```json
{ "mode": "auto" }
```

### POST /api/v1/commands/ack-alarm
```json
{ "alarm_id": "a123" }
```

### POST /api/v1/commands/reset-alarm
```json
{ "alarm_id": "a123" }
```

### POST /api/v1/commands/force-valve
Admin only.
```json
{ "valve_id": "v1", "position": "open" }
```

### POST /api/v1/commands/source-override
```json
{ "zone_id": "zone_peach_1", "source_mode": "well_direct" }
```

## 7. Telemetry

### GET /api/v1/telemetry/current
Returns summarized live values.

### GET /api/v1/telemetry/history
Query params:
- metric_key
- zone_id
- from
- to
- bucket optional

### GET /api/v1/state/map
Returns everything needed to render the live farm map:
- zone states
- pipeline states
- pump states
- source states
- freshness flags
- active alarms

## 8. Alarms

### GET /api/v1/alarms
Filters:
- status
- severity
- zone_id
- from
- to

### GET /api/v1/alarms/{alarmId}

### POST /api/v1/alarms/{alarmId}/ack
### POST /api/v1/alarms/{alarmId}/reset

## 9. Reports

Aggregated operational reports grounded in farm local time (`Africa/Tripoli`).

Query Parameters for all reports:
- `from_date` (YYYY-MM-DD): Start date in farm local time (default: today - 7 days)
- `to_date` (YYYY-MM-DD): End date in farm local time (default: today)
- `format` (json | csv): Data format (default: json). When `format=csv`, returns a CSV file with `text/csv; charset=utf-8` header and UTF-8 Byte Order Mark (`\ufeff`) so Excel renders Arabic characters cleanly.
- `lang` (ar | en): Language for CSV column headers. When `ar`, column headers are Arabic.

### GET /api/v1/reports/daily-irrigation
Aggregated daily water usage (m³) and cycle counts (total, completed, aborted, skipped).

### GET /api/v1/reports/water-usage
Aggregated water consumption and total runtimes per zone.

### GET /api/v1/reports/pump-runtime
Cumulative runtime hours and start counts per pump.

### GET /api/v1/reports/alarm-history
Historical alarm occurrences grouped by alarm code, severity, and bilingual title.

## 10. Admin

### GET /api/v1/users
### POST /api/v1/users
### PATCH /api/v1/users/{userId}
### GET /api/v1/system/config
### PATCH /api/v1/system/config

## 11. Response Rules

Use a standard response wrapper for commands:

```json
{
  "success": true,
  "command_id": "cmd_001",
  "status": "accepted",
  "message": "Zone start command accepted."
}
```

Error example:

```json
{
  "success": false,
  "error_code": "HYDRAULIC_CAPACITY_EXCEEDED",
  "message": "The requested zone combination is not allowed."
}
```

## 12. API Conventions

- never silently coerce invalid control requests
- expose reason codes for rejections
- return last-known state with freshness metadata
- keep `zone_id`, `device_id`, `alarm_id`, `command_id` stable across systems
