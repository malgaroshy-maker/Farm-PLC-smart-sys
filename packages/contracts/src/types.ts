/**
 * Algaroshy Farm — Shared Type Definitions
 *
 * Core interfaces used across backend, simulator, web, and mobile.
 * Derived from DOMAIN_MODEL.md, DATABASE_SCHEMA.md, API.md, and REALTIME_EVENTS.md.
 */

import type {
  SystemMode,
  ZoneState,
  ZoneHealth,
  CropType,
  WaterSourceType,
  SourceAvailability,
  PumpType,
  PumpState,
  ValveStatus,
  ValveCommand,
  SensorType,
  SensorScope,
  SignalQuality,
  CommandType,
  CommandStatus,
  ScheduleRecurrence,
  CycleOutcome,
  AlarmSeverity,
  AlarmCategory,
  AlarmStatus,
  AlarmSourceLayer,
  EventType,
  UserRole,
  ActorType,
} from "./enums.js";

// ─── Farm ───────────────────────────────────────────────

export interface Farm {
  id: string;
  name: string;
  name_ar: string;
  description: string;
  timezone: string;
  total_area_ha: number;
  created_at: string;
}

// ─── Zone ───────────────────────────────────────────────

export interface Zone {
  id: string;
  farm_id: string;
  code: string;
  name: string;
  name_ar: string;
  crop_type: CropType;
  area_ha: number;
  geometry_ref: string | null;
  enabled: boolean;
  priority: number;
  source_preference: WaterSourceType;
  allows_direct_well: boolean;
  max_runtime_min: number;
  default_duration_min: number;
  pressure_min_bar: number;
  pressure_max_bar: number;
  flow_min_m3h: number;
  flow_max_m3h: number;
}

export interface ZoneLiveState {
  zone_id: string;
  state: ZoneState;
  health: ZoneHealth;
  source_mode: WaterSourceType | null;
  pressure_bar: number | null;
  flow_m3h: number | null;
  moisture_pct: number | null;
  runtime_sec: number;
  active_alarm_count: number;
  last_updated: string;
}

// ─── Zone Combination ───────────────────────────────────

export interface ZoneCombination {
  id: string;
  zone_a_id: string;
  zone_b_id: string;
  allowed: boolean;
  notes: string;
}

// ─── Water Source ────────────────────────────────────────

export interface WaterSource {
  id: string;
  name: string;
  name_ar: string;
  type: WaterSourceType;
  enabled: boolean;
  availability: SourceAvailability;
}

// ─── Pump ───────────────────────────────────────────────

export interface Pump {
  id: string;
  farm_id: string;
  code: string;
  name: string;
  name_ar: string;
  pump_type: PumpType;
  rated_flow_m3h: number | null;
  rated_pressure_bar: number | null;
  runtime_hours: number;
  service_interval_hours: number;
  enabled: boolean;
}

export interface PumpLiveState {
  pump_id: string;
  state: PumpState;
  run_fb: boolean;
  fault: boolean;
  runtime_hours: number;
  last_updated: string;
}

// ─── Valve ──────────────────────────────────────────────

export interface Valve {
  id: string;
  zone_id: string;
  code: string;
  enabled: boolean;
  has_open_feedback: boolean;
  has_close_feedback: boolean;
}

export interface ValveLiveState {
  valve_id: string;
  status: ValveStatus;
  last_command: ValveCommand;
  last_updated: string;
}

// ─── Sensor ─────────────────────────────────────────────

export interface Sensor {
  id: string;
  farm_id: string;
  zone_id: string | null;
  code: string;
  sensor_type: SensorType;
  unit: string;
  location_scope: SensorScope;
  enabled: boolean;
}

export interface SensorReading {
  sensor_id: string;
  metric_key: string;
  value: number;
  unit: string;
  quality: SignalQuality;
  timestamp: string;
}

// ─── Schedule ───────────────────────────────────────────

export interface Schedule {
  id: string;
  zone_id: string;
  enabled: boolean;
  recurrence_rule: ScheduleRecurrence;
  start_time_local: string;
  duration_min: number;
  weekday_mask: number | null;
  season: string | null;
  priority: number;
  source_override: WaterSourceType | null;
  created_by: string;
  created_at: string;
  updated_at: string;
}

// ─── Irrigation Cycle ───────────────────────────────────

export interface IrrigationCycle {
  id: string;
  zone_id: string;
  source_mode: WaterSourceType;
  planned_start_at: string;
  actual_start_at: string | null;
  actual_end_at: string | null;
  planned_duration_min: number;
  actual_duration_min: number | null;
  outcome: CycleOutcome | null;
  water_estimate_m3: number | null;
  initiated_by_type: ActorType;
  initiated_by_id: string | null;
  notes: string;
  created_at: string;
}

// ─── Command ────────────────────────────────────────────

export interface Command {
  id: string;
  command_type: CommandType;
  target_type: string;
  target_id: string;
  payload: Record<string, unknown>;
  requested_by: string;
  status: CommandStatus;
  requested_at: string;
  acknowledged_at: string | null;
  completed_at: string | null;
  failure_reason: string | null;
}

export interface CommandResponse {
  success: boolean;
  command_id: string;
  status: CommandStatus;
  message: string;
  error_code?: string;
}

// ─── Alarm ──────────────────────────────────────────────

export interface Alarm {
  id: string;
  alarm_code: string;
  severity: AlarmSeverity;
  category: AlarmCategory;
  status: AlarmStatus;
  zone_id: string | null;
  device_type: string | null;
  device_id: string | null;
  source_layer: AlarmSourceLayer;
  current_value: number | null;
  threshold_value: number | null;
  triggered_at: string;
  acknowledged_at: string | null;
  acknowledged_by: string | null;
  cleared_at: string | null;
  reset_at: string | null;
  reset_by: string | null;
  message_ar: string;
  message_en: string;
  guidance_ar: string;
  guidance_en: string;
  correlation_key: string | null;
  requires_ack: boolean;
  requires_manual_reset: boolean;
}

// ─── Event Log ──────────────────────────────────────────

export interface EventLog {
  id: string;
  event_type: string;
  entity_type: string;
  entity_id: string;
  actor_type: ActorType;
  actor_id: string | null;
  payload: Record<string, unknown>;
  occurred_at: string;
}

// ─── Telemetry ──────────────────────────────────────────

export interface TelemetryPoint {
  id: string;
  metric_key: string;
  farm_id: string;
  zone_id: string | null;
  device_type: string | null;
  device_id: string | null;
  ts: string;
  value_numeric: number | null;
  value_text: string | null;
  quality: SignalQuality;
  source: string;
}

// ─── User ───────────────────────────────────────────────

export interface User {
  id: string;
  name: string;
  email: string | null;
  phone: string | null;
  role: UserRole;
  is_active: boolean;
  created_at: string;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  user: Pick<User, "id" | "name" | "role">;
}

// ─── Real-Time Event Envelope ───────────────────────────

export interface RealtimeEvent<T = unknown> {
  type: EventType;
  ts: string;
  payload: T;
}

// ─── Map State (API.md §7 - GET /state/map) ────────────

export interface FarmMapState {
  system_mode: SystemMode;
  zones: ZoneLiveState[];
  pumps: PumpLiveState[];
  valves: ValveLiveState[];
  sensors: SensorReading[];
  tank_level_pct: number;
  main_pressure_bar: number;
  main_flow_m3h: number;
  active_alarms: Alarm[];
  data_fresh: boolean;
  last_snapshot_ts: string;
}

// ─── Reports ────────────────────────────────────────────

export interface DailyIrrigationReport {
  date: string;
  cycles: IrrigationCycle[];
  total_water_m3: number;
  total_runtime_min: number;
  zones_watered: number;
}

export interface WaterUsageReport {
  zone_id: string;
  zone_name: string;
  period_start: string;
  period_end: string;
  total_water_m3: number;
  total_cycles: number;
}

export interface PumpRuntimeReport {
  pump_id: string;
  pump_name: string;
  period_start: string;
  period_end: string;
  total_runtime_hours: number;
  start_count: number;
  fault_count: number;
}
