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

There is no logout call: the app forgets its token. A token stops working when the account is switched off, its role or
password changes, or a backup is restored.

### GET /api/v1/auth/me
The signed-in user.

### POST /api/v1/auth/password
Any user. `{ "current_password": "...", "new_password": "..." }`. Ends every other sign-in of that user and returns a new
token. A wrong current password is `400 wrong_current_password` (limited like sign-in).

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

### POST /api/v1/zones/{zoneId}/maintenance-done
Records that maintenance was done on a zone.

Which zones may run together is stored in the database; there is no API for editing it.

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

### POST /api/v1/commands
One endpoint for every command:
```json
{ "command_type": "start_zone", "target_type": "zone", "target_id": "zone_enab", "payload": { "duration_min": 30 } }
```
`command_type`: `start_zone`, `stop_zone`, `stop_all`, `set_mode` (`payload.mode`), `reset_alarm`; in simulation only
also `inject_fault` and `set_panel`. `stop_all`, `set_mode` and `reset_alarm` use `target_type: "system"` with no
`target_id`.

A refused command is `409` with `{ "code": "...", "message": "...", "command_id": "..." }`.

A stop is never dropped: it stays pending until the controller confirms it, and ALM-052 is raised while it waits.

### GET /api/v1/commands?limit=20
Recent commands with their status (`pending`, `accepted`, `executing`, `completed`, `rejected`, `failed`, `timed_out`).

### GET /api/v1/commands/pending · PATCH /api/v1/commands/{id}/sync
Used by the controller gateway (service token only).

## 7. Telemetry

### GET /api/v1/telemetry/series
`metric_key`, optional `zone_id`, `minutes` (up to 7 days), `points`. Averaged history for charts.

### GET /api/v1/telemetry/flow-pressure

Returns main-line flow in m³/h and pressure in bar in shared one-minute buckets from the past hour. A missing measurement is `null`.

### GET /api/v1/telemetry/water-today

Returns `total_m3` and `zones` from farm-local midnight through the current farm time. Each zone has its `zone_id` and `m3` volume. The total and zone entries include `water_is_estimate` and `water_has_gaps`. A value is `null` when the volume is unknown and `0` when measured as zero. A run spanning midnight contributes only the volume supported by flow readings within today's portion.

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
- `from_date` (YYYY-MM-DD): Start date in farm local time. By default the report includes the last seven calendar dates through `to_date`.
- `to_date` (YYYY-MM-DD): End date in farm local time (default: today)
- `format` (json | csv): Data format (default: json). When `format=csv`, returns a CSV file with `text/csv; charset=utf-8` header and UTF-8 Byte Order Mark (`\ufeff`) so Excel renders Arabic characters cleanly.
- `lang` (ar | en): Language for CSV column headers. When `ar`, column headers are Arabic.

### GET /api/v1/reports/daily-irrigation
Aggregated daily water usage (m³) and cycle counts (total, completed, aborted, skipped).

### GET /api/v1/reports/water-usage
Aggregated water consumption and total runtimes per zone.

Both water reports group cycles by their farm-local start date. `total_water_m3` is `null` when no volume is known for the row and appears blank in CSV. A measured zero stays numeric. `water_is_estimate` indicates that the total includes an extrapolated cycle volume. `water_has_gaps` indicates incomplete or missing cycle readings. Both flags appear in JSON and CSV.

### GET /api/v1/reports/pump-runtime

Observed runtime hours and starts per pump. Runtime covers continuous intervals between fresh run-feedback samples. A start counts only when an observed stopped pump changes to running. An interruption in feedback breaks the interval, so the report leaves that time out of the totals. Dates use the farm calendar.

`history_status` is `complete`, `partial`, or `unavailable`, with `observed_seconds` and `window_seconds` giving the coverage. Missing totals are `null` in JSON and blank in CSV. `history_source` identifies simulation or controller history. The report keeps those histories separate. Pump faults count alarms with the corresponding pump's recorded device ID.

### GET /api/v1/reports/alarm-history
Historical alarm occurrences grouped by alarm code, severity, and bilingual title.

## 10. Users, system and records

### Users (admin only)
- `GET /api/v1/users`
- `POST /api/v1/users` `{ "name", "username", "role", "password" }`. Roles: `owner_admin`, `operator`, `viewer`.
  Usernames are not case-sensitive. Passwords: at least 8 characters, at most 72 bytes.
- `PATCH /api/v1/users/{id}` any of `name`, `username`, `role`, `password`, `is_active`.

Accounts are switched off, not deleted. The last active admin cannot be switched off or demoted (`409 last_admin`).
A locked-out owner resets a password on the farm PC: `python -m app.reset_password <username>` in `apps/api`.

### System
- `GET /api/v1/system/health` checks of the database, controller link, scheduler, AI, weather, disk and backup.
- `GET /api/v1/system/features` · `PUT /api/v1/system/features/{key}` (admin)
- `GET /api/v1/system/notifications` · `PUT .../notifications/telegram` · `POST .../notifications/telegram/detect` ·
  `POST .../notifications/test` (admin)
- `GET /api/v1/system/push/public-key` · `POST .../push/subscribe` · `POST .../push/unsubscribe`

### Soil
- `GET /api/v1/soil/levels` · `PUT /api/v1/soil/levels/{cropType}` · `GET /api/v1/soil/status`
- `GET /api/v1/soil/probes` · `POST /api/v1/soil/probes` · `DELETE /api/v1/soil/probes/{id}`
- `POST /api/v1/ingest/soil` readings from the probe gateway.

### Backups (admin)
- `GET /api/v1/backups` · `POST /api/v1/backups` · `POST /api/v1/backups/{name}/restore` (applied at the next start) ·
  `DELETE /api/v1/backups/restore`

### Event log
- `GET /api/v1/events?limit&before_id&category&entity_id` records of commands, alarms, sign-ins and changes.

### Simulation only
- `GET|POST /api/v1/sim/clock` · `GET /api/v1/sim/scenarios` · `POST /api/v1/sim/scenarios/{name}/run` ·
  `POST /api/v1/sim/scenarios/stop`

## 11. AI and Weather (Milestone E)

### POST /api/v1/ai/explain-alarm (also /ai/alarm-assistant)
Explains an alarm using live sensor and catalog context.
```json
{ "alarm_id": "alm_...", "alarm_code": "ALM-008", "language": "ar", "question": "..." }
```
The answer holds a summary, likely causes, steps and a safety note in Arabic and English, and names the provider.

### POST /api/v1/ai/chat
Chat with read-only farm tools (`get_alarm`, `get_zone_state`, `get_recent_telemetry`, `get_cycles`, `get_schedule`,
`get_forecast`). It cannot start or stop water.
```json
{ "message": "كم استهلكنا من الماء اليوم؟", "language": "ar", "context_zone_id": null, "history": [] }
```

### GET /api/v1/ai/suggestions
Returns pending and historical weather-aware irrigation suggestions.

### POST /api/v1/ai/suggestions/{id}/approve
Approves a suggestion (Operator+). Weather advice becomes a one-day program change. A soil "extra run" starts the
zone at once, only while it has not expired and the soil is still confirmed dry.

### POST /api/v1/ai/suggestions/{id}/undo
Takes back an approved one-day change that no run has used.

### POST /api/v1/ai/suggestions/{id}/reject
Rejects an advisor suggestion with feedback.

### GET /api/v1/ai/briefing
Returns the daily morning briefing for the specified farm date (default: today).
Query parameter: `date=YYYY-MM-DD`.

### GET /api/v1/ai/weather/forecast
Returns cached Open-Meteo weather forecast for Algaroshy Farm (`32.516250, 14.070361`, Africa/Tripoli).

### GET /api/v1/ai/settings
Admin endpoint returning provider order, feature toggles, API key status, and active models.

### PUT /api/v1/ai/settings
Admin endpoint to update AI configuration.

### POST /api/v1/ai/test
Admin endpoint testing connectivity, measuring latency, and returning the active model.

## 12. API Conventions

- never silently coerce invalid control requests
- expose reason codes for rejections
- return last-known state with freshness metadata
- keep `zone_id`, `device_id`, `alarm_id`, `command_id` stable across systems

## Security rules (2026-11-27)

- `POST /api/v1/auth/login`: after 10 failed attempts for a username within 1 minute the API answers `429` with a `Retry-After` header.
- `POST /api/v1/system/push/subscribe`: the endpoint must be an HTTPS address of a browser push service (Google, Mozilla, Apple or Microsoft); anything else gets `422`.
- `POST /api/v1/system/push/unsubscribe`: removes only the caller's own device, unless the caller is an admin.
- `stop_all` ends any irrigation program that is running. The event log records `program.cancelled`.
