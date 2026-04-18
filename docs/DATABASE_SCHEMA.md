# DATABASE_SCHEMA.md

## 1. Database Strategy

Use a relational database for configuration, commands, alarms, and reports.  
Use a telemetry table strategy that supports time-series inserts.

Prototype options:
- SQLite for local simulation
- PostgreSQL for team/dev/staging/production

## 2. Core Tables

### farms
- id PK
- name
- description
- timezone
- created_at
- updated_at

### users
- id PK
- name
- email nullable
- phone nullable
- password_hash or auth_provider fields
- role
- is_active
- created_at
- updated_at

### zones
- id PK
- farm_id FK
- code unique
- name
- crop_type
- geometry_ref
- enabled
- priority
- source_preference
- allows_direct_well
- max_runtime_min
- default_duration_min
- pressure_min_bar
- pressure_max_bar
- flow_min_m3h
- flow_max_m3h
- created_at
- updated_at

### zone_combinations
Defines whether two zones may run together.
- id PK
- zone_a_id FK
- zone_b_id FK
- allowed
- notes
- created_at

### pumps
- id PK
- farm_id FK
- code unique
- name
- pump_type
- rated_flow nullable
- rated_pressure nullable
- runtime_hours
- service_interval_hours
- enabled
- created_at
- updated_at

### valves
- id PK
- zone_id FK
- code unique
- enabled
- has_open_feedback
- has_close_feedback
- created_at
- updated_at

### sensors
- id PK
- farm_id FK
- zone_id nullable
- code unique
- sensor_type
- unit
- location_scope
- enabled
- calibration_meta_json
- created_at
- updated_at

### schedules
- id PK
- zone_id FK
- enabled
- recurrence_rule
- start_time_local
- duration_min
- weekday_mask nullable
- season nullable
- priority
- source_override nullable
- created_by FK users
- created_at
- updated_at

### commands
- id PK
- command_type
- target_type
- target_id
- payload_json
- requested_by FK users
- status
- requested_at
- acknowledged_at nullable
- completed_at nullable
- failure_reason nullable

### irrigation_cycles
- id PK
- zone_id FK
- source_mode
- planned_start_at
- actual_start_at
- actual_end_at
- planned_duration_min
- actual_duration_min
- outcome
- initiated_by_type
- initiated_by_id nullable
- water_estimate_m3 nullable
- notes
- created_at

### alarms
- id PK
- alarm_code
- severity
- category
- status
- zone_id nullable
- device_type nullable
- device_id nullable
- source_layer
- current_value nullable
- threshold_value nullable
- triggered_at
- acknowledged_at nullable
- acknowledged_by nullable FK users
- cleared_at nullable
- reset_at nullable
- reset_by nullable FK users
- message_ar
- message_en
- guidance_ar
- guidance_en
- correlation_key nullable

### event_logs
- id PK
- event_type
- entity_type
- entity_id
- actor_type
- actor_id nullable
- payload_json
- occurred_at

## 3. Telemetry Tables

### telemetry_points
Generic append-only table.
- id PK
- metric_key
- farm_id FK
- zone_id nullable
- device_type nullable
- device_id nullable
- ts
- value_numeric nullable
- value_text nullable
- quality
- source

Index recommendations:
- (metric_key, ts desc)
- (zone_id, ts desc)
- (device_id, ts desc)

### device_state_snapshots
Optional denormalized current-state cache.
- device_key PK
- state_json
- updated_at

## 4. Report Materialization Tables (Optional)
For performance later:
- report_daily_zone_usage
- report_daily_pump_runtime
- report_daily_alarm_counts

## 5. Example Metric Keys

- `tank.level_pct`
- `main.pressure.bar`
- `main.flow.m3h`
- `pump.well.run_fb`
- `pump.booster.run_fb`
- `zone.<id>.moisture_pct`
- `zone.<id>.active`
- `zone.<id>.runtime_sec`

## 6. Event Sourcing Rule

All important control changes should create event log entries even if a current-state table also exists.

Examples:
- command requested
- command accepted/rejected
- cycle started/stopped
- alarm active/cleared/acked/reset
- schedule created/edited/deleted
- user login for audit-sensitive environments
