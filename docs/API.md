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

## 5. Schedules

### GET /api/v1/schedules
### POST /api/v1/schedules
Create schedule.
```json
{
  "zone_id": "zone_olive_1",
  "recurrence_rule": "FREQ=DAILY",
  "start_time_local": "06:00",
  "duration_min": 45,
  "season": "summer",
  "priority": 1
}
```

### PATCH /api/v1/schedules/{scheduleId}
### DELETE /api/v1/schedules/{scheduleId}

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

### GET /api/v1/reports/daily-irrigation
### GET /api/v1/reports/water-usage
### GET /api/v1/reports/pump-runtime
### GET /api/v1/reports/alarm-history

Export parameter:
- `format=csv|xlsx|pdf` where implemented

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
