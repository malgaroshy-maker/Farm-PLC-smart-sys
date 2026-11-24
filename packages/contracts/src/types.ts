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
  /** planned run length for the current cycle */
  target_runtime_sec?: number;
  active_alarm_count: number;
  /** G7: panel selector switch (auto · on · off) */
  panel_mode?: "auto" | "on" | "off";
  /** G7: who started the current run */
  run_source?: "app" | "fallback" | "panel" | "resume" | null;
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
  pump_type?: PumpType;
  state: PumpState;
  run_fb: boolean;
  fault: boolean;
  runtime_hours: number;
  starts_today?: number;
  /** G7: panel selector switch (auto · hand · off) */
  panel_mode?: "auto" | "hand" | "off";
  /** G7 pump health */
  power_kw?: number;
  energy_kwh_today?: number;
  current_a?: number;
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
  zone_id?: string;
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

// ─── Programs & Steps (Milestone D) ───────────────────────

export interface ProgramStep {
  id: string;
  program_id: string;
  zone_id: string;
  step_order: number;
  duration_min: number;
  created_at: string;
  updated_at: string;
}

export interface ProgramStepCreate {
  zone_id: string;
  step_order: number;
  duration_min: number;
}

export interface Program {
  id: string;
  name: string;
  enabled: boolean;
  start_time_local: string; // HH:MM in farm local time (Africa/Tripoli)
  weekday_mask: string; // e.g. "1,2,3,4,5,6,7" (1=Monday ... 7=Sunday)
  season: string | null;
  notes: string | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
  steps: ProgramStep[];
  total_duration_min: number;
}

export interface ProgramCreate {
  name: string;
  enabled?: boolean;
  start_time_local: string;
  weekday_mask?: string;
  season?: string | null;
  notes?: string | null;
  steps: ProgramStepCreate[];
}

export interface ProgramUpdate {
  name?: string;
  enabled?: boolean;
  start_time_local?: string;
  weekday_mask?: string;
  season?: string | null;
  notes?: string | null;
  steps?: ProgramStepCreate[];
}

export interface ConflictError {
  code: string;
  message_en: string;
  message_ar: string;
  details?: Record<string, unknown>;
}

export interface NextIrrigationInfo {
  program_id: string;
  program_name: string;
  step_order: number;
  zone_id: string;
  zone_name: string;
  crop_type?: string;
  scheduled_start_farm: string;
  duration_min: number;
  seconds_until_start: number;
}

// ─── Irrigation Cycle ───────────────────────────────────

export interface IrrigationCycle {
  id: string;
  zone_id: string;
  source_mode: WaterSourceType;
  program_id?: string | null;
  program_step_id?: string | null;
  command_id?: string | null;
  planned_start_at: string | null;
  actual_start_at: string | null;
  actual_end_at: string | null;
  planned_duration_min: number | null;
  actual_duration_min: number | null;
  outcome: CycleOutcome | null;
  water_estimate_m3: number | null;
  water_is_estimate?: boolean;
  initiated_by_type: ActorType;
  initiated_by_id: string | null;
  alarms_json?: string | null;
  failure_reason?: string | null;
  notes: string | null;
  created_at: string;
}

// ─── Command ────────────────────────────────────────────

export interface Command {
  id: string;
  command_type: CommandType;
  target_type: string;
  target_id: string | null;
  payload: Record<string, unknown> | null;
  requested_by: string | null;
  actor_type: ActorType;
  status: CommandStatus;
  requested_at: string;
  acknowledged_at: string | null;
  completed_at: string | null;
  failure_reason: string | null;
}

/** Body sent with POST /commands */
export interface CommandRequest {
  command_type: CommandType;
  target_type: string;
  target_id?: string | null;
  payload?: Record<string, unknown> | null;
}

/** 409 body when an interlock blocks a command (the command is still recorded as rejected) */
export interface CommandRejection {
  code: string;
  message: string;
  command_id: string;
}

// ─── Alarm ──────────────────────────────────────────────

export interface Alarm {
  id: string;
  alarm_code: string;
  name: string;
  name_ar: string | null;
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
  message_ar: string | null;
  message_en: string | null;
  guidance_ar: string | null;
  guidance_en: string | null;
  /** true while the underlying condition is still present (false = latched) */
  condition_active: boolean;
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
  username: string;
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
  token_type: "bearer";
  user: AuthUser;
}

export interface AuthUser {
  id: string;
  username: string;
  name: string;
  role: UserRole;
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
  last_snapshot_ts: string | null;
  farm_now?: string;
  speed?: number;
  clock_mode?: "real" | "sim";
  clock_paused?: boolean;
  /** G7: mains power at the panel */
  power_ok?: boolean;
  /** G7: the PLC is running its own copy of today's program (app unreachable) */
  fallback_active?: boolean;
  /** G7: water above the well pump intake (m) */
  well_level_m?: number | null;
  /** G7: pressure drop across the head-unit filter (bar) */
  filter_dp_bar?: number | null;
}

// ─── Simulation Clock ───────────────────────────────────

export interface FarmClockState {
  mode: "real" | "sim";
  speed: number;
  paused: boolean;
  farm_now: string;
  real_now: string;
  action?: string;
}

export interface ClockUpdateRequest {
  speed?: number;
  pause?: boolean;
  step_min?: number;
  jump_to?: string;
  real?: boolean;
  confirm?: boolean;
}

// ─── Reports ────────────────────────────────────────────

export interface DailyIrrigationReportRow {
  date: string;
  total_water_m3: number;
  cycle_count: number;
  completed_count: number;
  aborted_count: number;
  skipped_count: number;
  faulted_count: number;
  manual_stop_count: number;
  total_duration_min: number;
}

export interface WaterUsageReportRow {
  zone_id: string;
  zone_name: string;
  zone_name_ar: string;
  crop_type: CropType | string;
  total_water_m3: number;
  cycle_count: number;
  completed_count: number;
  total_duration_min: number;
}

export interface PumpRuntimeReportRow {
  pump_id: string;
  pump_name: string;
  pump_name_ar: string;
  pump_type: string;
  start_count: number;
  runtime_hours: number;
  faults_count: number;
}

export interface AlarmHistoryReportRow {
  alarm_code: string;
  count: number;
  severity: string;
  title: string;
  title_ar: string;
}

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

// ─── Telemetry history (GET /telemetry/series) ─────────

export interface SeriesPoint {
  ts: string;
  value: number;
  min: number;
  max: number;
}

export interface TelemetrySeries {
  metric_key: string;
  zone_id: string | null;
  minutes: number;
  points: SeriesPoint[];
}

// ─── Simulation scenarios (GET /sim/scenarios) ─────────

export interface ScenarioInfo {
  name: string;
  title: string;
  title_ar: string;
  description: string;
  expect: string[];
  steps: number;
}

export interface ScenarioRun {
  name: string | null;
  status: "idle" | "running" | "passed" | "failed" | "stopped";
  step: number;
  total: number;
  message: string;
  started_at: string | null;
  finished_at: string | null;
  log: string[];
}
