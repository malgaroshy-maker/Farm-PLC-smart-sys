# 📅 Schedules, Scheduler, Cycle Log & Reports — Specification

**Status:** In Progress (Milestone D Steps 1–4)  
**Author:** Algaroshy Farm Project Team  
**Date:** 2026-11-19  

This document records the owner's decisions and technical architecture for Milestone D steps 1–4 of the Algaroshy Farm Smart Irrigation System: program-based schedules, the farm-clock scheduler service, the end-to-end irrigation cycle log, and reporting with CSV exports.

---

## 1. Owner Decisions

| # | Topic | Owner Decision | Rationale |
|---|---|---|---|
| 1 | **Schedule shape** | **Programs (Ordered Zone Sequences)**: A named program with a start time and days of the week, running an ordered list of zones and durations sequentially (one after another). | `max_concurrent_zones = 1` enforces single-zone operation. Programs naturally prevent self-overlap, streamline daily cycles across tree blocks, and match real farming operations. |
| 2 | **Overlaps** | **Reject at save time with conflict message**: If two programs would overlap in time across any day or midnight boundary, reject creation/update with structured AR/EN conflict details. | Explicit scheduling eliminates hidden queuing confusion and guarantees deterministic hydraulic execution. |
| 3 | **Blocked start** | **Skip zone, log, raise S1 info alarm, continue program**: When an interlock blocks a step (critical alarm, tank < 15%, zone busy, system not auto), skip that zone, log `schedule.skipped`, raise an S1 info alarm, and proceed to the next step. | Keeps remaining crops irrigated without halting the entire multi-zone sequence, while maintaining full visibility and audit trail. |
| 4 | **Missed runs** | **Skip and log "missed"**: If the API was offline or the farm clock jumped past a scheduled start time, mark as missed and do not mass-fire backlogged runs. | Prevents water hammer, tank depletion, and cascading commands when advancing the simulation clock or recovering from restarts. |
| 5 | **Schedules page layout** | **Day Timeline + Edit Drawer**: 24-hour visual bar for each day of the week with colored program blocks, plus a slide-over edit drawer for program details and step sequencing. | Gives operators an instant visual overview of daily water allocation and dead bands, with quick touch editing. |
| 6 | **Permissions** | **Operator+ toggle, Admin create/edit**: Operators and Admins can enable/disable existing programs; only Admins can create, edit, or delete programs. | Empowers daily farm operators to pause schedules during rain or field work while protecting hydraulic parameters from unintended changes. |
| 7 | **Cycle log scope** | **All runs (Manual, Scheduled, Scenario)**: Record every irrigation run in `irrigation_cycles` regardless of initiator. | Complete audit trail for water accounting, compliance, and accurate comparison between planned vs actual water consumption. |
| 8 | **Reports page layout** | **Single page with tabs**: Daily Irrigation, Water per Zone, Pump Runtime, Alarm History tabs with date range picker, summary cards, Recharts visualizations, data tables, and CSV exports. | Unified analytics dashboard without disjointed navigation. |
| 9 | **CSV export language** | **Arabic headers when UI is in Arabic (UTF-8 with BOM)**: Export with localized column headers matching the active language, prepending UTF-8 BOM (`\ufeff`) for Microsoft Excel compatibility. | Direct compatibility with farm management spreadsheets in Libya without character corruption. |
| 10 | **Dashboard integration** | **Next Irrigation Card**: Add a live countdown card to the dashboard side column and phone status view (program name, zone name/crop, start time, live countdown on farm clock). | Operators immediately know when the next automatic cycle starts without navigating away from the overview map. |

---

## 2. Architecture & Data Model

### 2.1 Database Schema (`programs` & `program_steps`)
To support ordered sequences while respecting existing database structures, we introduce `programs` and `program_steps` via an Alembic migration:

```sql
CREATE TABLE programs (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    start_time_local VARCHAR(10) NOT NULL, -- "06:00" in Africa/Tripoli
    weekday_mask VARCHAR(30) NOT NULL DEFAULT "1,2,3,4,5,6,7", -- 1=Monday ... 7=Sunday
    season VARCHAR(20),
    notes TEXT,
    created_by VARCHAR(64) REFERENCES users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE program_steps (
    id VARCHAR(64) PRIMARY KEY,
    program_id VARCHAR(64) NOT NULL REFERENCES programs(id) ON DELETE CASCADE,
    zone_id VARCHAR(64) NOT NULL REFERENCES zones(id),
    step_order INTEGER NOT NULL,
    duration_min INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE scheduler_state (
    key VARCHAR(64) PRIMARY KEY, -- e.g. "last_farm_date" or program-step cursor
    value_text TEXT,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

### 2.2 Irrigation Cycle Schema Updates (`irrigation_cycles`)
The existing `irrigation_cycles` table is enhanced to track linked programs, commands, and alarms:
- `program_id`: VARCHAR(64) nullable (references `programs.id`)
- `program_step_id`: VARCHAR(64) nullable (references `program_steps.id`)
- `command_id`: VARCHAR(64) nullable (references `commands.id`)
- `alarms_json`: TEXT nullable (JSON list of alarm codes raised during run)
- `failure_reason`: TEXT nullable

### 2.3 Monotonic Program Run State
To survive API restarts, speed changes (up to 360×), pauses, and clock jumps:
- `program_runs` / `scheduler_state` table records the latest completed/active execution window for each program per farm date.
- Stored as `last_fired_at` (farm datetime) and `active_run` state.

---

## 3. Conflict Checker (Pure Function)

Located in `apps/api/app/services/conflicts.py`:
- Pure, deterministic, asynchronous/synchronous helper.
- Evaluates:
  1. **Temporal Overlaps**: Computes the `[start, end]` interval in farm-local minutes for each program occurrence across all 7 weekdays. Checks if any interval overlaps another enabled program (including wraps past midnight).
  2. **Zone Max Runtime**: Verifies each step's `duration_min` $\le$ `zone.max_runtime_min`.
  3. **Hydraulic Interlocks**: Checks forbidden zone combinations if concurrency was ever > 1 (today strictly `max_concurrent_zones = 1`).
  4. **Disabled Zones**: Warns or errors if a program includes an inactive/disabled zone.
- Returns structured conflict items with error codes and bilingual messages (AR & EN).

---

## 4. Scheduler Service (`apps/api/app/services/scheduler.py`)

1. **Clock Integration**:
   - Ticks inside `Monitor.tick()` using `clock.farm_now()`.
   - Never uses real wall-clock timeouts or external unanchored timers.
2. **Execution Logic**:
   - Identifies programs scheduled for today's farm weekday that are due between `last_tick_farm_time` and `current_farm_time`.
   - If the time gap between ticks exceeds 15 farm minutes (e.g. clock jump or API outage), applies the **Missed Runs** rule: marks the run as `missed`, emits `schedule.missed`, and does not fire commands.
3. **Step Execution & Sequencing**:
   - Initiates Step 1 via `commands.submit_command(..., actor=Actor(actor_id="scheduler", role="operator", actor_type="scheduler"))`.
   - Monitors zone command status. Moves to Step 2 **only after** the previous zone is back to `idle` (off) and its command status is terminal (`completed`, `failed`, or `stopped`).
   - If a step is rejected or blocked by an interlock: executes the **Blocked Start** rule (logs `schedule.skipped`, raises S1 info alarm, advances to the next step).
4. **Events & Broadcasts**:
   - Emits WebSocket events: `program.started`, `program.step_started`, `program.step_completed`, `schedule.skipped`, `schedule.missed`, `program.finished`.

---

## 5. Irrigation Cycle Log (`apps/api/app/services/cycles.py`)

- **Trigger Points**:
  - `start_zone` command accepted $\rightarrow$ creates `irrigation_cycles` row with status `executing`, `actual_start_at = clock.farm_now()`.
  - Zone transitions to `off` / `idle` $\rightarrow$ closes cycle with `actual_end_at = clock.farm_now()`, computes `actual_duration_min`, trapezoidal volume integration $m^3$ from `zone.flow_m3h` telemetry, outcome (`completed`, `manual_stop`, `aborted`, `faulted`), and links any alarm codes raised.
- **Clock Jump Handling**:
  - When the farm clock jumps, the simulator stops active zones. The cycle recorder sets `outcome = "aborted"` with note `"clock jump"`.
- **Water Today Alignment**:
  - `telemetry.water_today` queries closed cycle volumes for today plus the trapezoidal integration of any currently running cycle, ensuring Dashboard and Reports match 100%.

---

## 6. Reports & CSV Export (`apps/api/app/routers/reports.py`)

Endpoints:
1. `GET /api/v1/reports/daily-irrigation?from=YYYY-MM-DD&to=YYYY-MM-DD&format=json|csv`
2. `GET /api/v1/reports/water-usage?from=YYYY-MM-DD&to=YYYY-MM-DD&zone_id=...&format=json|csv`
3. `GET /api/v1/reports/pump-runtime?from=YYYY-MM-DD&to=YYYY-MM-DD&format=json|csv`
4. `GET /api/v1/reports/alarm-history?from=YYYY-MM-DD&to=YYYY-MM-DD&severity=...&format=json|csv`

CSV Export:
- Output begins with UTF-8 BOM bytes `\xef\xbb\xbf`.
- Headers translated to Arabic when request header `Accept-Language: ar` or parameter `lang=ar` is provided.

---

## 7. Web UI & Dashboard

1. **Schedules Page (`/schedules`)**:
   - 7-day timeline view with 24-hour horizontal bands.
   - Program blocks visually sized by total run duration with crop icons and colors.
   - Drawer editor: program name, start time picker, weekday selector, ordered step list with drag/order controls, duration chips (15/30/45/60 min) + slider.
   - Real-time conflict validation banner before saving.
   - Enable/disable toggle accessible to operators and admins; create/edit restricted to admins.
2. **Reports Page (`/reports`)**:
   - Tabs: Daily Irrigation, Water Usage, Pump Runtime, Alarm History.
   - Date range selector presets (Today, Yesterday, Last 7 Days, Last 30 Days).
   - Recharts bar/line charts and interactive tables with CSV export button.
3. **Dashboard Next Irrigation Card**:
   - Positioned in dashboard side column and mobile quick-status card.
   - Displays: Program Name, Next Zone, Scheduled Time, and live ticking countdown based on `useFarmClock()`.
