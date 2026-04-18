# DOMAIN_MODEL.md

## 1. Core Domain Objects

### Farm
Represents Algaroshy Farm as a whole.
Fields:
- id
- name
- description
- timezone
- created_at

### Zone
Logical irrigation area controlled as one unit in phase 1.
Fields:
- id
- farm_id
- code
- name
- crop_type
- geometry_ref
- enabled
- priority
- source_preference
- allows_direct_well
- max_runtime_min
- default_duration_min
- seasonal_multiplier_profile_id
- pressure_min_bar
- pressure_max_bar
- flow_min_m3h
- flow_max_m3h

### ZoneGroup
Optional grouping of zones for scheduling/reporting.
Examples:
- olives
- pomegranate
- grapes
- fruit trees

### WaterSource
Represents tank, direct-well, or future source modes.
Fields:
- id
- name
- type (`tank`, `well_direct`, `hybrid`)
- enabled
- notes

### Pump
Fields:
- id
- code
- name
- type (`well`, `booster`)
- run_feedback
- fault_feedback
- runtime_hours
- service_interval_hours

### Valve
Fields:
- id
- zone_id
- code
- type
- open_feedback
- close_feedback
- last_command
- status

### Sensor
Fields:
- id
- code
- type (`pressure`, `flow`, `level`, `moisture`, `power`, `weather`)
- zone_id nullable
- device_scope (`mainline`, `zone`, `tank`, `source`)
- unit
- online
- last_value
- last_timestamp

### Schedule
Fields:
- id
- zone_id
- enabled
- recurrence
- start_time
- duration_min
- season
- priority
- source_override nullable

### IrrigationCycle
One execution instance.
Fields:
- id
- zone_id
- source_id
- started_at
- ended_at
- planned_duration_min
- actual_duration_min
- outcome (`completed`, `aborted`, `faulted`, `manual_stop`)
- water_estimate_m3

### Alarm
Defined in `ALARM_MATRIX.md`.

### EventLog
General immutable audit/event record.
Fields:
- id
- event_type
- entity_type
- entity_id
- actor_type
- actor_id
- payload
- occurred_at

### User
Fields:
- id
- name
- email/phone
- role
- active

## 2. State Models

### Zone Operational State
- off
- scheduled
- starting
- running
- paused
- stopping
- completed
- warning
- fault
- manual_override

### System Mode
- off
- auto
- manual
- maintenance

### Command Status
- pending
- accepted
- rejected
- executing
- completed
- failed
- timed_out

## 3. Relationship Notes

- one farm has many zones
- one zone may have one or more valves later, but phase 1 assumes one logical control valve
- one farm has multiple pumps and sensors
- one zone has many schedules and cycles
- alarm may belong to system, source, pump, sensor, or zone
- event logs are append-only and should not be edited

## 4. Derived Concepts

### Zone Health
Computed from:
- active command/state agreement
- pressure in safe band
- flow in safe band
- moisture trend
- valve feedback
- alarm presence

### Source Availability
Computed from:
- tank level
- dry-run risk
- pump availability
- source mode config

### Telemetry Freshness
Computed by comparing current time to last update time for each tag/device.

## 5. Geometry Model

The farm map layer should use:
- `geometry_ref` for polygons
- path definitions for pipelines
- placement definitions for tank, well, pump house, and labels

A lightweight map model should include:
- zone polygons
- pipeline segments
- node points
- device markers
- animation paths
