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

### schedule.fired
Emitted when a scheduled program or step is due and fires.

### schedule.skipped
Emitted when an interlock or safety constraint blocks a scheduled start (e.g. low tank, open critical alarm). Accompanied by reason and S1 info alarm.

### schedule.missed
Emitted when the farm clock jumped past a scheduled run or an API outage occurred. Recorded as missed without mass-firing.

### program.started
Emitted when an automated irrigation program begins execution.

### program.finished
Emitted when an automated irrigation program completes all its sequential steps.

### program.step_started
Emitted when a specific zone step in a program begins.

### program.step_completed
Emitted when a program step completes and zone returns to idle before next step.

### cycle.started
Emitted when an irrigation cycle begins (manual, scheduled, or scenario).

### cycle.ended
Emitted when an irrigation cycle concludes with duration, outcome, and integrated water usage (m³).

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
