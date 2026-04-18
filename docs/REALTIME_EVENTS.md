# REALTIME_EVENTS.md

## 1. Purpose

Define the live events used by:
- web app
- Android app
- simulator
- notification triggers
- state synchronization

Transport options:
- WebSocket for apps
- MQTT optional for device/edge integration

## 2. Event Types

### state.snapshot
Initial full state on connect.

### zone.state.changed
Emitted whenever a zone changes state.

### pump.state.changed
Emitted for run/fault/status changes.

### sensor.value.updated
Emitted when a tracked value changes significantly or by sampling rule.

### alarm.active
### alarm.cleared
### alarm.acknowledged
### alarm.reset

### command.updated
Lifecycle change of a command.

### telemetry.stale
Marks data no longer fresh.

### system.mode.changed
System off/auto/manual/maintenance change.

## 3. Envelope

```json
{
  "type": "zone.state.changed",
  "ts": "2026-04-18T10:20:00Z",
  "payload": {}
}
```

## 4. Payload Examples

### zone.state.changed
```json
{
  "type": "zone.state.changed",
  "ts": "2026-04-18T10:20:00Z",
  "payload": {
    "zone_id": "zone_olive_1",
    "previous_state": "starting",
    "current_state": "running",
    "source_mode": "tank",
    "pressure_bar": 2.7,
    "flow_m3h": 4.1,
    "moisture_pct": 33.2,
    "health": "healthy"
  }
}
```

### pump.state.changed
```json
{
  "type": "pump.state.changed",
  "ts": "2026-04-18T10:20:02Z",
  "payload": {
    "pump_id": "pump_booster_01",
    "run_fb": true,
    "fault": false,
    "runtime_hours": 183.4
  }
}
```

### sensor.value.updated
```json
{
  "type": "sensor.value.updated",
  "ts": "2026-04-18T10:20:04Z",
  "payload": {
    "sensor_id": "main_pressure_01",
    "metric_key": "main.pressure.bar",
    "value": 2.75,
    "unit": "bar",
    "quality": "good"
  }
}
```

### telemetry.stale
```json
{
  "type": "telemetry.stale",
  "ts": "2026-04-18T10:25:00Z",
  "payload": {
    "scope": "system",
    "reason": "no_updates_within_threshold",
    "last_good_ts": "2026-04-18T10:23:01Z"
  }
}
```

## 5. Client Rules

- UI must handle out-of-order arrival defensively
- `state.snapshot` should be applied before incremental events
- stale indicator must be visually obvious
- events should update map, alarms, and tables without full page reload

## 6. Optional MQTT Topics

```text
farm/state/zone/{zoneId}
farm/state/pump/{pumpId}
farm/state/sensor/{sensorId}
farm/alarm/{alarmCode}
farm/system/mode
```
