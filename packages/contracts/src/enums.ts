/**
 * Algaroshy Farm — Shared Enums
 *
 * Central enum definitions used across backend, simulator, web, and mobile.
 * Derived from PRD.md, DOMAIN_MODEL.md, ALARM_MATRIX.md, PLC_CONTROL_LOGIC.md, and AI_FEATURES.md.
 */

// ─── System ─────────────────────────────────────────────

/** System operating mode (PLC_CONTROL_LOGIC.md §2) */
export type SystemMode = "off" | "auto" | "manual" | "maintenance";

/** Deployment runtime mode (ARCHITECTURE.md §3) */
export type DeploymentMode =
  | "simulation"
  | "local_pilot"
  | "production_hybrid";

// ─── Zones ──────────────────────────────────────────────

/** Zone operational state machine (PLC_CONTROL_LOGIC.md §12) */
export type ZoneState =
  | "off"
  | "queued"
  | "starting_pump"
  | "opening_valve"
  | "validating_flow"
  | "running"
  | "stopping"
  | "completed"
  | "warning"
  | "faulted";

/** Zone health derived status (DOMAIN_MODEL.md §4) */
export type ZoneHealth =
  | "healthy"
  | "degraded"
  | "warning"
  | "critical"
  | "unknown";

/** Crop type for zone classification */
export type CropType =
  | "pomegranate"
  | "olives"
  | "grapes"
  | "mixed_fruit"
  | "other";

// ─── Water Sources ──────────────────────────────────────

/** Water source type (DOMAIN_MODEL.md §1) */
export type WaterSourceType = "tank" | "well_direct" | "hybrid";

/** Source availability status */
export type SourceAvailability =
  | "available"
  | "unavailable"
  | "degraded"
  | "dry_run_risk";

// ─── Pumps ──────────────────────────────────────────────

/** Pump type */
export type PumpType = "well" | "booster";

/** Pump state machine (PLC_CONTROL_LOGIC.md §12) */
export type PumpState =
  | "stopped"
  | "starting"
  | "running"
  | "failed_start"
  | "faulted"
  | "cooldown";

// ─── Valves ─────────────────────────────────────────────

/** Valve status */
export type ValveStatus = "open" | "closed" | "opening" | "closing" | "fault" | "unknown";

/** Valve command */
export type ValveCommand = "open" | "close" | "none";

// ─── Sensors ────────────────────────────────────────────

/** Sensor type (DOMAIN_MODEL.md §1) */
export type SensorType =
  | "pressure"
  | "flow"
  | "level"
  | "moisture"
  | "power"
  | "weather";

/** Sensor location scope */
export type SensorScope = "mainline" | "zone" | "tank" | "source";

/** Signal quality */
export type SignalQuality = "good" | "degraded" | "bad" | "stale" | "unknown";

// ─── Commands ───────────────────────────────────────────

/** Command type */
export type CommandType =
  | "start_zone"
  | "stop_zone"
  | "stop_all"
  | "set_mode"
  | "ack_alarm"
  | "reset_alarm"
  | "force_valve"
  | "source_override";

/** Command lifecycle status (DOMAIN_MODEL.md §2) */
export type CommandStatus =
  | "pending"
  | "accepted"
  | "rejected"
  | "executing"
  | "completed"
  | "failed"
  | "timed_out";

// ─── Schedules ──────────────────────────────────────────

/** Schedule recurrence */
export type ScheduleRecurrence = "once" | "daily" | "weekly" | "seasonal";

/** Irrigation cycle outcome (DOMAIN_MODEL.md §1) */
export type CycleOutcome =
  | "completed"
  | "aborted"
  | "faulted"
  | "manual_stop";

// ─── Alarms (ALARM_MATRIX.md) ───────────────────────────

/** Alarm severity (ALARM_MATRIX.md §3) */
export type AlarmSeverity = "S0" | "S1" | "S2" | "S3";

/** Alarm category (ALARM_MATRIX.md §4) */
export type AlarmCategory =
  | "process"
  | "equipment"
  | "utility"
  | "water_source"
  | "configuration"
  | "security"
  | "maintenance";

/** Alarm status lifecycle (ALARM_MATRIX.md §5) */
export type AlarmStatus =
  | "pending"
  | "active_unacked"
  | "active_acked"
  | "cleared"
  | "suppressed";

/** Alarm source layer */
export type AlarmSourceLayer = "plc" | "backend" | "derived";

// ─── Real-Time Events (REALTIME_EVENTS.md) ──────────────

/** WebSocket event type */
export type EventType =
  | "state.snapshot"
  | "zone.state.changed"
  | "pump.state.changed"
  | "sensor.value.updated"
  | "alarm.active"
  | "alarm.cleared"
  | "alarm.acknowledged"
  | "alarm.reset"
  | "command.updated"
  | "telemetry.stale"
  | "system.mode.changed"
  | "ai.suggestion.new"
  | "ai.anomaly.detected"
  | "ai.weather.advisory"
  | "ai.insight.ready"
  | "ai.maintenance.alert";

// ─── Users & Roles (PRD.md §6) ─────────────────────────

/** User role */
export type UserRole = "owner_admin" | "operator" | "viewer";

/** Actor type for event sourcing */
export type ActorType = "user" | "system" | "scheduler" | "plc" | "ai";

// ─── Reports ────────────────────────────────────────────

/** Report export format */
export type ReportFormat = "csv" | "xlsx" | "pdf";

// ─── Notification ───────────────────────────────────────

/** Notification channel */
export type NotificationChannel = "push" | "web" | "email" | "sms";

// ─── AI Features (AI_FEATURES.md) ───────────────────────

/** AI feature module identifier */
export type AIFeature =
  | "alarm_assistant"
  | "smart_scheduling"
  | "predictive_maintenance"
  | "anomaly_detection"
  | "weather_advisor"
  | "water_optimizer"
  | "daily_insights"
  | "crop_vision"
  | "voice_control"
  | "seasonal_learning";

/** AI service availability mode */
export type AIServiceMode = "online" | "offline_fallback" | "disabled";

/** AI suggestion status lifecycle */
export type AISuggestionStatus =
  | "pending"
  | "accepted"
  | "rejected"
  | "expired"
  | "auto_applied";

/** AI suggestion priority */
export type AISuggestionPriority = "low" | "medium" | "high" | "urgent";

/** Anomaly type detected by AI (AI_FEATURES.md §4) */
export type AnomalyType =
  | "slow_leak"
  | "pipe_burst"
  | "sensor_stuck"
  | "phantom_consumption"
  | "unusual_pattern"
  | "pressure_anomaly"
  | "flow_anomaly"
  | "consumption_anomaly";

/** Anomaly severity */
export type AnomalySeverity = "info" | "warning" | "critical";

/** Weather condition category (AI_FEATURES.md §5) */
export type WeatherCondition =
  | "clear"
  | "cloudy"
  | "rain_light"
  | "rain_heavy"
  | "thunderstorm"
  | "wind_strong"
  | "heatwave"
  | "frost_risk"
  | "high_humidity"
  | "sandstorm";

/** Weather advisory action */
export type WeatherAction =
  | "skip_irrigation"
  | "extend_duration"
  | "reduce_duration"
  | "delay_irrigation"
  | "emergency_protect"
  | "no_action";

/** Equipment health score band (AI_FEATURES.md §3) */
export type EquipmentHealth =
  | "excellent"   // 80-100
  | "good"        // 60-79
  | "fair"        // 40-59
  | "poor"        // 20-39
  | "critical";   // 0-19

/** AI insight/report type (AI_FEATURES.md §7) */
export type InsightType =
  | "daily_summary"
  | "weekly_summary"
  | "water_efficiency"
  | "maintenance_advisory"
  | "scheduling_optimization"
  | "anomaly_summary";

/** AI insight delivery channel */
export type InsightDelivery = "dashboard" | "push" | "email";

/** Voice command intent (AI_FEATURES.md §9) */
export type VoiceIntent =
  | "start_zone"
  | "stop_zone"
  | "stop_all"
  | "query_status"
  | "query_report"
  | "set_mode"
  | "unknown";

/** Supported AI language */
export type AILanguage = "ar" | "en";
