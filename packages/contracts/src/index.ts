/**
 * Algaroshy Farm — Shared Contracts
 *
 * Barrel export for all shared types, enums, alarm definitions, and seed data.
 * Import from "@algaroshy/contracts" in web, mobile, and test packages.
 */

// Enums
export * from "./enums.js";

// Type interfaces
export * from "./types.js";

// Alarm definitions
export { ALARM_DEFINITIONS } from "./alarms.js";
export type { AlarmDefinition } from "./alarms.js";

// Seed data
export {
  FARM_SEED,
  ZONE_SEEDS,
  PUMP_SEEDS,
  SOURCE_SEEDS,
  SENSOR_SEEDS,
  VALVE_SEEDS,
} from "./seeds.js";
