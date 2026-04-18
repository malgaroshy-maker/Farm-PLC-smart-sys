/**
 * Algaroshy Farm — AI Feature Type Definitions
 *
 * Interfaces for all 10 AI features defined in AI_FEATURES.md.
 */

import type {
  AIFeature,
  AIServiceMode,
  AISuggestionStatus,
  AISuggestionPriority,
  AnomalyType,
  AnomalySeverity,
  WeatherCondition,
  WeatherAction,
  EquipmentHealth,
  InsightType,
  InsightDelivery,
  VoiceIntent,
  AILanguage,
  ActorType,
} from "./enums.js";

// ─── AI Service Config ──────────────────────────────────

export interface AIServiceConfig {
  feature: AIFeature;
  enabled: boolean;
  mode: AIServiceMode;
  model_id: string;
  max_tokens: number;
  temperature: number;
  fallback_enabled: boolean;
}

// ─── AI Suggestion (Generic) ────────────────────────────

export interface AISuggestion {
  id: string;
  feature: AIFeature;
  priority: AISuggestionPriority;
  status: AISuggestionStatus;
  title: string;
  title_ar: string;
  description: string;
  description_ar: string;
  reasoning: string;
  reasoning_ar: string;
  action_payload: Record<string, unknown> | null;
  zone_id: string | null;
  device_id: string | null;
  confidence: number;
  created_at: string;
  expires_at: string | null;
  responded_at: string | null;
  responded_by: string | null;
}

// ─── Feature 1: AI Alarm Assistant ──────────────────────

export interface AlarmAssistantQuery {
  query: string;
  language: AILanguage;
  context_alarm_ids: string[];
  context_zone_id: string | null;
}

export interface AlarmAssistantResponse {
  id: string;
  query: string;
  language: AILanguage;
  response_text: string;
  diagnosis: string;
  suggested_actions: AlarmAssistantAction[];
  related_alarm_codes: string[];
  confidence: number;
  source: "gemini" | "fallback_template";
  created_at: string;
}

export interface AlarmAssistantAction {
  step: number;
  action: string;
  action_ar: string;
  is_automated: boolean;
  command_payload: Record<string, unknown> | null;
}

// ─── Feature 2: Smart Scheduling ────────────────────────

export interface AIScheduleSuggestion {
  id: string;
  zone_id: string;
  suggested_start_time: string;
  suggested_duration_min: number;
  current_duration_min: number;
  reason: string;
  reason_ar: string;
  signals: ScheduleSignal[];
  status: AISuggestionStatus;
  confidence: number;
  created_at: string;
}

export interface ScheduleSignal {
  signal_type: string;
  value: number;
  unit: string;
  weight: number;
  description: string;
}

// ─── Feature 3: Predictive Maintenance ──────────────────

export interface MaintenancePrediction {
  id: string;
  device_type: string;
  device_id: string;
  device_name: string;
  device_name_ar: string;
  health_score: number;
  health_band: EquipmentHealth;
  risk_score: number;
  estimated_days_to_failure: number | null;
  trend_direction: "improving" | "stable" | "declining" | "critical";
  metrics: MaintenanceMetric[];
  recommendation: string;
  recommendation_ar: string;
  last_analyzed_at: string;
}

export interface MaintenanceMetric {
  metric_key: string;
  current_value: number;
  baseline_value: number;
  deviation_pct: number;
  trend: "up" | "down" | "stable";
  unit: string;
}

// ─── Feature 4: Anomaly Detection ───────────────────────

export interface DetectedAnomaly {
  id: string;
  anomaly_type: AnomalyType;
  severity: AnomalySeverity;
  zone_id: string | null;
  device_id: string | null;
  description: string;
  description_ar: string;
  evidence: AnomalyEvidence[];
  ai_explanation: string | null;
  ai_explanation_ar: string | null;
  is_active: boolean;
  is_false_positive: boolean;
  detected_at: string;
  resolved_at: string | null;
  dismissed_by: string | null;
}

export interface AnomalyEvidence {
  metric_key: string;
  expected_value: number;
  actual_value: number;
  deviation: number;
  unit: string;
  timestamp: string;
}

// ─── Feature 5: Weather Advisor ─────────────────────────

export interface WeatherData {
  timestamp: string;
  temperature_c: number;
  humidity_pct: number;
  wind_speed_kmh: number;
  wind_direction: string;
  precipitation_mm: number;
  precipitation_probability_pct: number;
  uv_index: number;
  condition: WeatherCondition;
  description: string;
  description_ar: string;
}

export interface WeatherForecast {
  current: WeatherData;
  hourly: WeatherData[];
  daily: WeatherDaySummary[];
  last_fetched_at: string;
  source: string;
}

export interface WeatherDaySummary {
  date: string;
  temp_min_c: number;
  temp_max_c: number;
  humidity_avg_pct: number;
  precipitation_total_mm: number;
  precipitation_probability_pct: number;
  condition: WeatherCondition;
  description: string;
  description_ar: string;
}

export interface WeatherAdvisory {
  id: string;
  condition: WeatherCondition;
  action: WeatherAction;
  affected_zone_ids: string[];
  message: string;
  message_ar: string;
  valid_from: string;
  valid_until: string;
  auto_applied: boolean;
  created_at: string;
}

// ─── Feature 6: Water Usage Optimizer ───────────────────

export interface WaterOptimization {
  id: string;
  suggested_zone_groups: ZoneGroup[];
  estimated_water_savings_pct: number;
  estimated_energy_savings_pct: number;
  estimated_pump_cycle_reduction: number;
  reasoning: string;
  reasoning_ar: string;
  confidence: number;
  created_at: string;
}

export interface ZoneGroup {
  group_id: number;
  zone_ids: string[];
  suggested_order: number;
  total_flow_m3h: number;
  total_duration_min: number;
  notes: string;
}

// ─── Feature 7: Daily AI Insights ───────────────────────

export interface AIInsightReport {
  id: string;
  insight_type: InsightType;
  language: AILanguage;
  date: string;
  title: string;
  title_ar: string;
  summary: string;
  summary_ar: string;
  sections: InsightSection[];
  suggestions: AISuggestion[];
  delivery: InsightDelivery[];
  generated_at: string;
  generated_by: "gemini" | "stats_only";
}

export interface InsightSection {
  heading: string;
  heading_ar: string;
  content: string;
  content_ar: string;
  icon: string;
  metrics: InsightMetric[];
}

export interface InsightMetric {
  label: string;
  label_ar: string;
  value: number;
  unit: string;
  change_pct: number | null;
  trend: "up" | "down" | "stable";
}

// ─── Feature 8: Crop Health Vision ──────────────────────

export interface CropVisionAnalysis {
  id: string;
  zone_id: string;
  image_url: string;
  analysis_text: string;
  analysis_text_ar: string;
  health_score: number;
  issues_detected: CropIssue[];
  recommendations: string[];
  recommendations_ar: string[];
  analyzed_at: string;
  model_used: string;
}

export interface CropIssue {
  type: "stress" | "pest" | "disease" | "nutrient_deficiency" | "dry_spot" | "overwatering";
  severity: AnomalySeverity;
  location_description: string;
  confidence: number;
}

// ─── Feature 9: Voice Control ───────────────────────────

export interface VoiceCommandRequest {
  audio_data: string;
  language: AILanguage;
  user_id: string;
}

export interface VoiceCommandResponse {
  id: string;
  transcript: string;
  intent: VoiceIntent;
  entities: Record<string, unknown>;
  response_text: string;
  response_audio_url: string | null;
  command_id: string | null;
  confidence: number;
  processed_at: string;
}

// ─── Feature 10: Seasonal Learning ──────────────────────

export interface SeasonalModel {
  id: string;
  zone_id: string;
  crop_type: string;
  season: string;
  year: number;
  moisture_baseline: number;
  optimal_duration_min: number;
  optimal_frequency_days: number;
  water_per_cycle_m3: number;
  data_points_count: number;
  confidence: number;
  last_updated_at: string;
}

export interface SeasonalRecommendation {
  id: string;
  zone_id: string;
  season: string;
  current_settings: Record<string, unknown>;
  recommended_settings: Record<string, unknown>;
  expected_improvement_pct: number;
  reasoning: string;
  reasoning_ar: string;
  based_on_years: number;
  created_at: string;
}

// ─── AI Dashboard State ─────────────────────────────────

export interface AIDashboardState {
  service_mode: AIServiceMode;
  features_enabled: AIFeature[];
  active_suggestions_count: number;
  active_anomalies_count: number;
  active_weather_advisories_count: number;
  last_insight_at: string | null;
  equipment_health_summary: {
    excellent: number;
    good: number;
    fair: number;
    poor: number;
    critical: number;
  };
  weather_summary: WeatherData | null;
  ai_actions_today: number;
  ai_savings_estimate: {
    water_saved_pct: number;
    energy_saved_pct: number;
  };
}
