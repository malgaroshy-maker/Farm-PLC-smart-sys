# Changelog

All notable changes to the Algaroshy Farm Smart Irrigation System will be documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/).

---

## [Unreleased]

### Milestone D second review fixes (2026-11-19)
- **API restart no longer catches up missed runs.** On the first tick after start-up, every program start between the last recorded tick and now is logged as `schedule.missed` (owner decision #4) instead of being fired.
- **Timed-out starts close their cycle.** A start nobody picked up is now closed as `aborted` with the timeout reason, the same as failed and superseded starts.
- **No invented water.** A run whose flow was measured as zero records 0 m³, not an estimate. A single sample is extrapolated and flagged `water_is_estimate`. The zone's nominal flow is never used.
- Regression tests for all three (API 122).

### Milestone D Review Follow-up & Fixes (2026-11-19)
- **Reports Query Parameters & Date Range:**
  - Standardized date query parameters on `from_date` and `to_date` (matching `docs/API.md`), retaining backward-compatible `from` and `to` aliases.
  - Enforced inclusive farm-local dates: Today = 1 day, Last 7 Days = 7 days (`to_d - timedelta(days=6)`), Last 30 Days = 30 days. Added tests for date ranges and aliases.
- **Cycle Count Breakdown & No-NaN Guarantee:**
  - Expanded `/reports/daily-irrigation` to return per-day cycle breakdown: `cycle_count`, `completed_count`, `aborted_count`, `skipped_count`, `faulted_count`, and `manual_stop_count`.
  - Added shared types `DailyIrrigationReportRow`, `WaterUsageReportRow`, `PumpRuntimeReportRow`, `AlarmHistoryReportRow` to `@algaroshy/contracts`.
  - Frontend `Reports.tsx` uses typed fallback logic, ensuring cycle totals add up correctly and completely eliminating `NaN`.
- **ALM-045 for Blocked Scheduled Starts:**
  - Introduced `ALM-045` ("Scheduled step skipped / تم تخطي خطوة مجدولة"): S1 severity, category `schedule`, momentary, no ack or reset required, with bilingual Arabic/English guidance.
  - Kept `alarm_catalog.py`, `@algaroshy/contracts` (`alarms.ts`, `enums.ts`), and `docs/ALARM_MATRIX.md` in sync (verified by `test_contracts_sync.py`).
  - Blocked scheduled starts raise `ALM-045` (never security violation `ALM-035`), log a skipped cycle with failure reason, and advance to the next step.
- **Scenario Program Cleanup (`prog_scen_*`):**
  - Added `cleanup_scenario_programs(db)` purging all scenario programs, steps, and scheduler state.
  - Executed in `ScenarioRunner._run` inside a `finally` block (covering both pass and fail paths), API lifespan startup, and `reset_demo.py`.
- **Missed Run Detection on Real Elapsed Time:**
  - Replaced arbitrary 900s farm gap threshold with real wall-clock downtime detection (`delta_real_sec > 60.0`) and explicit clock jump signals (`self._pending_jump` via `on_clock_jump`).
  - Simulation ticks at 360× execute all due runs in `(prev_farm_time, now_farm_time]` without incorrectly tagging them as missed. Real jumps or downtime mark missed runs.
- **Cycle Lifecycle & Terminal Command Sync:**
  - Added `record_cycle_aborted_by_command` ensuring commands that fail, time out, or are superseded before zone state changes close their cycle as `aborted` with `failure_reason` exactly once.
  - Reset and "Back to real time" guarantee 0 open cycles remain.
- **Water Volume Estimation Flag (`water_is_estimate`):**
  - Created Alembic migration `4e1f8d2a3c5b` adding `water_is_estimate` boolean column to `irrigation_cycles`.
  - In `integrate_zone_water_m3`: computes trapezoidal volume with $\ge 2$ telemetry flow samples (`water_is_estimate = False`); with $< 2$ samples, estimates volume and sets `water_is_estimate = True`.
  - UI `ZoneDrawer.tsx` displays `≈` on estimated cycle volumes. Water today and reports use aligned calculations.
- **Localization & Bundle Chunk Optimization:**
  - Translated hard-coded strings in Reports and Schedules via `lib/i18n.ts`.
  - Lazy-loaded `ReportsPage`, `SchedulesPage`, and `SimulatorPanel` via `React.lazy()` and `Suspense`. Main Vite bundle chunk reduced from **839.33 kB** (with chunk warning) to **339.19 kB** (zero chunk warnings).
- **Verification:**
  - 118 API pytest tests passed.
  - 27 Simulator pytest tests passed.
  - 36 Web Vitest tests passed.
  - Full live verification from `run.bat reset` with Playwright: UI 3-zone program creation, execution at 360× with 0 missed runs, blocked start interlock ALM-045 and continuation, clean scenario `prog_scen_*` removal, Reports presets with 0 NaN and UTF-8 BOM Arabic CSV downloads, zone drawer history with `≈` estimates, and return to real time with 0 open cycles.

### Milestone D (Steps 1–4) — Sequential programs, scheduler, cycle log, reports (2026-11-19)
- **Sequential Irrigation Programs:**
  - Owner-approved architecture in [docs/SCHEDULES.md](docs/SCHEDULES.md). Data model (`programs`, `program_steps`, `scheduler_state`) in Alembic migration `3d9f8e2a1b4c`.
  - CRUD API (`/api/v1/schedules`) with permissions (Operator+ can enable/disable, Admin creates/edits/deletes).
  - Strict conflict checker (`app/services/conflicts.py`): pure function validating max concurrent zones (`1`), 24 h total runtime limits, zone max runtimes, weekday overlaps across midnight and Sunday-to-Monday wraparound, forbidden zone combinations, and pump capacity. Returns structured bilingual AR/EN conflict details.
  - Live `/api/v1/schedules/upcoming?hours=24` endpoint feeding dashboard next-irrigation card.
- **Scheduler Service (Farm Clock):**
  - Runs on the virtual farm clock (`clock.farm_now()`) driven by the monitor loop (`app/services/scheduler.py`). Removed unused `apscheduler` dependency.
  - Persists last-fired timestamps per step in `scheduler_state` table to survive API restarts without double-firing.
  - Issues zone commands strictly through `submit_command` with `actor_type="scheduler"`, ensuring all physical and hydraulic interlocks apply.
  - Advances to the next step only after the previous zone reaches idle/off.
  - Handles pause, speed changes (up to 360×), and monotonic clock jumps (aborts active run, updates anchor time, prevents mass-firing).
  - Blocked-start interlock policy: skips blocked zone, records `skipped` cycle, raises S1 info alarm (`ALM-045`), and continues the program.
  - WebSocket broadcasts: `schedule.fired`, `schedule.skipped`, `schedule.missed`, `program.started`, `program.finished`.
- **Irrigation Cycle Log:**
  - Complete run history in `irrigation_cycles` (`/api/v1/cycles`).
  - Records planned vs actual start/end/duration in farm time, initiator (`actor_type`, `actor_id`), speed-aware trapezoidal water volume integration (`zone.flow_m3h`), outcome (`completed`, `aborted`, `faulted`, `manual_stop`, `skipped`), and linked alarm codes.
  - Integrated with state sync (`app/routers/state.py`) on zone completion, fault, or abort.
  - Embedded recent cycle history in the Zone Drawer with status chips, duration, and water usage.
- **Reports & CSV Export:**
  - Reports API (`/api/v1/reports`): daily irrigation, water usage per zone, pump runtime, and alarm history. Date ranges scoped to Tripoli local time.
  - Bilingual CSV export with UTF-8 BOM (`\xef\xbb\xbf`) and Arabic/English headers for seamless Excel support.
  - Web Reports page (`/reports`) featuring Recharts charts, formatted data tables, date range presets, empty states, and CSV downloads.
  - Added duotone `ScheduleIcon` and `ReportsIcon` in `FarmIcons.tsx`.
- **Dashboard Next Irrigation Card:**
  - Added Next Irrigation card in the dashboard side panel and mobile status card.
  - Ticks smoothly on `useFarmClock()` showing upcoming program, zone, time, and countdown.
- **Simulator Scenarios:**
  - `scheduled_day`: Creates a 3-zone program, jumps to 5 min before start, runs at 60×, and asserts 3 completed cycles with water > 0.
  - `scheduled_blocked_start`: Validates low tank interlock skipping, S1 alarm ALM-035 generation, and subsequent direct-well step execution.
- **Verification:** 112 API tests, 27 simulator tests, 32 web tests (171 total tests green). Live Playwright run verified program creation, conflict validation, execution on map at 60×, cycle log recording, next-irrigation card ticking, report generation, and UTF-8 BOM CSV export.

### Simulation time — virtual farm clock (2026-11-19)
- **Shared Virtual Farm Clock:** Single source of truth in the API (`app/core/clock.py`), persisted via Alembic migration (`farm_clock` table). Monotonic progression, locked to real time unless `CONTROLLER_MODE=simulator`.
- **Clock Endpoints & Events:** `GET /api/v1/sim/clock` and `POST /api/v1/sim/clock` (admin only in simulation mode). Audit events (`clock.speed_changed`, `clock.paused`, `clock.resumed`, `clock.stepped`, `clock.jumped`, `clock.reset_to_real`) and real-time WebSocket broadcast `clock.changed`.
- **Separation of Clocks:** Farm-facing timestamps (`telemetry.ts`, `alarm.triggered_at/cleared_at/acknowledged_at/reset_at`, `event.occurred_at`, `command.requested_at/completed_at`, ALM-036 24h window, water-today midnight, telemetry retention) use `clock.farm_now()`. Link-health checks (comms staleness, command timeouts, JWT expiry, debounce) stay on real wall clock (`utcnow()`), with AST guard test enforcing separation.
- **Telemetry Throttling & Speed-Aware Gap Limit:** Persisted every 10 s of farm time, at most 1 row/s real time, with farm timestamps and sample speed stored in `value_text`. `water_today` dynamically calculates `max_gap_s` based on sample speed (`max(60.0, 3.0 * max(10.0, speed * 1.0))`), dropping 10-minute outages at 1× while integrating normal 360 s spacing at 360×.
- **Simulator Dynamic Following:** Simulator connects to `clock.changed` and `state.snapshot` events over WebSocket. Physics `dt = real_dt × speed` with sub-stepping; pause suspends physics while continuing sensor publication; jumps stop running zones and apply closed-form soil drying and tank balance. `TIMESCALE` in `.env` sets initial speed only.
- **"Back to Real Time":** Confirmation modal explaining history will be cleared; invokes `reset_history()` and resets virtual clock to Tripoli wall clock at 1×.
- **Web UI:**
  - `useFarmClock()` hook with local sub-second tick interpolation across header clock, map lighting, tree seasonal sprites, chart labels, and event times.
  - Amber `#ff9f43` SIMULATED TIME badge with speed (e.g. `⏩ 360× · وقت محاكاة` / `SIMULATED TIME`) shown beside every clock when simulated.
  - Presenter-mode header chip on desktop (play/pause, 1×/10×/60×/360×, step +1 min, quick jump popover) collapsing to badge on phones.
  - Full Virtual Farm Clock control panel on the Simulator page with digital clock, playback, speeds, presets, custom jump, and "Back to real time".
- **Verification & Review Follow-up Fixes:** 86 API tests, 27 simulator tests, 29 Vitest tests, 3 map-model tests (145 total green). Review resolved blocker and correctness issues:
  - Fixed blocker in `apps/simulator/src/engine.py` where `jump()` set `pump.state = "off"`, preventing restarts (now set to `"stopped"`, preserving tripped faults, `run_fb=False`, `pump_t.clear()`, and `phase_t`/`zone_abort`/`zone_cmd` reset for stopped zones). Added forward and backward jump regression tests.
  - Unified command times with API as single source of farm time (`clock.farm_now()` stamped in `sync_command`, controller timestamps ignored, simulator timestamps removed). Clamped timestamps so `completed_at >= acknowledged_at >= requested_at`. Fixed `CommandResponse._decode_payload` early return that bypassed `as_utc` timestamp normalization when payload was None. Tested at 360× across both two-step (`accepted` -> `completed`) and direct terminal sync.
  - Redacted token from WebSocket log in `client.py:98`, logging only the host.
  - Fixed `scenarios.py` `wait_alarm` to compare farm time `Alarm.triggered_at` against farm time `_started_farm`, keeping real time for step timeouts. Removed duplicate return in `reset_all_cleared` and removed all references to `normal_day` alias across codebase and docs in favor of `normal_cycle`.
  - Reverted `0356f537da66_initial_schema.py` to master formatting, excluded `alembic/versions/` from `ruff format`, removed `screenshots/` and `scripts/test_live_check.py`, and added `screenshots/` to `.gitignore`.
  - Live execution verified with single simulator at 10× and 1×: zone start → running → jump to 05:30 → stopped → start again → reaches running → Back to real time → start again → reaches running → Event log command times strictly ordered.

### Maintenance sign-off + clean demo reset (2026-11-18)
- **"Maintenance done"** for a zone (operator+). It's in the zone panel and on ALM-036 in the Alarm Center, with an optional note. `POST /api/v1/zones/{id}/maintenance-done` writes a `zone.maintenance_done` event. Faults before that moment stop counting towards ALM-036 (repeated faults), so the alarm clears on the next sync instead of hanging for 24 h. New faults count again from zero. Covered by a test.
- **`run.bat reset`** (or `./run.sh reset`, which can be combined with `demo`) clears alarms, commands, the event log, telemetry and state snapshots before starting. Users, passwords, zones and settings are kept. It can also be run on its own: `python -m app.reset_demo`.
- The Alarm Center shows zone names instead of ids.

### UI round 2 — map realism, animation, dashboard, styling (2026-11-18)
**Map**
- About 3,200 individual tree sprites, drawn on a canvas layer at real row spacing and row direction for each crop (pomegranate, olive, trellis grape, peach/apricot/plum rows). Fruit follows the real season: each crop has a fruiting and a green sprite, chosen by the farm-local month. Dry zones yellow tree by tree.
- Irrigating zones show damp soil spreading under each tree, expanding cyan rings and drip sparkles.
- Camera fly-to when a zone is selected, and auto-focus on a new S2/S3 alarm. The rest of the farm dims, and a "back to farm" button appears.
- Glass label chips with a live badge (moisture, flow + time left, or the alarm code) and a pointer tooltip. A pulsing severity ring marks an alarmed zone, and faulted equipment glows.
- Life on the farm: a tractor working a track, birds crossing now and then, and a worker who walks the tracks to the valve of an unacknowledged zone alarm and stays there until it is handled.
- Fix: valve markers on the map and in the zone panel now show the real valve state. The API's live valve state has no `zone_id`, so the old lookup never matched.

**Dashboard & panels**
- Map + side column: tank gauge with a wave, pumps, the top active alarms, and trends (tank 24 h, flow & pressure 1 h, water used today by zone). Phones get a status card first.
- New `GET /api/v1/telemetry/water-today`: m³ per zone since farm-local midnight, integrated from flow telemetry (with test).
- Zone panel redesigned in the order status → controls → history → crop & hardware. Starting a zone uses a duration picker (preset chips 15/30/45/60, a slider up to the zone's max runtime, default = the zone's usual duration) with a confirm step. The chosen duration is sent as `payload.duration_min`.
- Header: alarm-chime mute and reduce-motion toggles, remembered per viewer. Reduce motion also follows the OS setting and turns off the farm-life and water animations. A short WebAudio chime plays on new S2/S3 alarms.

**Style & assets**
- Duotone line icon set (navigation, equipment, crops) replaces the generic icons.
- Glass panels across all pages.
- New photoreal art, generated through the ChatGPT/Codex subscription: crop detail images in the zone panel, pump art on the Equipment page, a golden-hour login aerial, and calm empty-state images for alarms and events.

### Start script (2026-11-18)
- New one-window launcher (`scripts/start.mjs`, wrapped by `run.bat` / `run.sh`). It starts the API, simulator and web app with tagged logs, waits until live data flows, then opens the browser.
- First run sets itself up: `.env` with generated secrets (admin login printed once), Python venv and requirements (reinstalled when they change), `pnpm install`, database migration and seed.
- **`API_PORT` in `.env` is now the single source** for the API port. Previously `run.bat` hardcoded 8000 while the simulator and web proxy read other settings, so they could disagree and nothing connected. The launcher stops early with a clear message if a port is taken.
- Ctrl+C or closing the window kills every process tree it started. The old `--reload` setup could leave orphaned API workers holding the port. `stop.bat` / `stop.sh` act as a safety net and only touch this app's processes.
- `run.bat demo`: production build, LAN/phone URLs printed, installable PWA.
- `--smoke` self-test. Verified in this checkout (dev + demo) and in a fresh clone with nothing installed.
- `.gitattributes` keeps `.sh` LF and `.bat` CRLF.

### Milestone C — Demo-quality UI + PWA (2026-11-18)
**Map**
- Zone geometry traced from the owner's sketch by line colour and flood fill, and verified against the legend areas (all 15 features within ±12%). New `@algaroshy/map-model` package with tests. Tooling and README are in `tools/map-geometry/`.
- Plausible mainline network, valves, dirt tracks and equipment positions, editable in `network.py`.
- Photoreal assets generated through the owner's ChatGPT/Codex subscription: 4 crop textures, sand, track, tank, booster, control room, wellhead and logo. Optimised from 44 MB to 636 KB WebP.
- New animated SVG map: per-zone crop texture rotated to the row direction, flow animation scaled to real flow, wet soil while irrigating, dry-canopy tint, pump rotors, valve symbols, tank gauge, day/night with lamps, zoom/pan.

**UI**
- Arabic by default with full RTL and an English toggle (`lib/i18n.ts`). Bundled Arabic font. Logo and branding. Farm-local clock.
- New Zones, Equipment and Event log pages. New `GET /api/v1/events` endpoint (filters, pagination, actor names).
- Presenter mode: the Simulator page is hidden unless an admin switches it on.
- Responsive phone layout (bottom nav, slide-in menu) and an installable PWA. The service worker never caches `/api` or `/ws`.
- The zone drawer closes on Escape. Redesigned KPI tiles. Bidi-safe numbers in RTL.

**Data**
- The mixed-fruit zone's third crop is **plum (عوينة)**, not guava. Fixed in the seed, the contracts and an Alembic data migration that only touches the untouched seed name.

**Tests**: 69 API, 22 simulator, 17 web, 3 map-model.

### Milestone B — Credible simulator + real alarms (2026-11-18)
**Simulator (acts as the PLC and the farm)**
- Loads zones, pumps, valves and sensors from the API, with per-zone flow and pressure limits.
- Timed sequences per PLC_CONTROL_LOGIC §3: starting pump → opening valve (travel time) → validating flow → running → stopping. Zones stop on their own at the cycle duration. Start commands now finish as `completed` only once the zone is really running, or `failed` if the start was aborted.
- Physics: a VFD booster that holds a pressure setpoint until demand exceeds its curve, emitter flow that follows √pressure, a tank mass balance with well refill (hysteresis), direct-well supply for allowed zones when the tank is low, soil moisture that rises while irrigating and dries out over the day, and seeded sensor noise (deterministic runs).
- PLC protection with real consequences: pump trip, failed start, valve stuck closed or open, blocked line (no flow), mainline leak, critical tank level, e-stop and tank sensor fault. The simulator reports active conditions to the backend as `plc_alarms`.
- Fault injection for pumps, valves, zones, the mainline, the tank sensor, the tank level and communications.

**Alarm engine (backend)**
- 20 alarm codes from ALARM_MATRIX with AR/EN messages and operator guidance. A test keeps them in sync with `@algaroshy/contracts`.
- Lifecycle: active_unacked → active_acked → latched until ack/reset → cleared. One open instance per correlation key, re-armed if the condition comes back.
- Derived rules: tank low (ALM-001), low/high pressure only while irrigating (ALM-008/010), manual and maintenance mode (ALM-042/043), stale data and comms lost (ALM-044/029), repeated faults on a zone (ALM-036), unauthorized command attempts (ALM-035).
- New interlock: an open critical (S3) alarm blocks zone starts until it is cleared and reset.
- API: `GET /alarms?view=active|history`, `POST /alarms/{id}/ack` (operator+), `POST /alarms/{id}/reset` (admin). Alarm events go out over WebSocket, and the snapshot includes active alarms.

**Scenarios & history**
- Scenario runner with 13 scripted scenarios from SIMULATION_PLAN §5. They run through the normal command service, so interlocks and the audit trail apply. Endpoints: `/sim/scenarios`, `/sim/scenarios/{name}/run`, `/sim/scenarios/stop`.
- Telemetry history is sampled every 10 s and kept for 7 days. `GET /telemetry/series` returns bucket-averaged series.

**Web**
- Alarm Center: active and history views, severity colours per the matrix (the previous S0/S3 mapping was backwards), expandable AR/EN guidance, ack/reset by role.
- Zone drawer: real moisture and flow history (1h/6h/24h), source, valve state, cycle progress, zone alarms.
- New Simulator page: scenarios with live progress and log, fault buttons, system mode, tank level.
- Map shows starting/stopping zones. The header alarm badge takes the colour of the worst severity. New main-pressure KPI.

**Bugs found by running every scenario against the live stack** (each now has a regression test)
- Leak detection missed leaks on large zones, because a fixed max-flow band hid them. It now compares the mainline meter with the emitters' expected flow at the current pressure.
- A start the controller never finished (e.g. after a simulator restart) blocked all other zones for 180 s. A stop now supersedes open starts, and the simulator fails a start that was stopped early.
- A persistent fault (valve stuck across retries) kept one alarm open, so the repeated-fault rule never triggered. It now also counts controller-aborted starts.
- Scenario waits could be satisfied by snapshots from before the command. They now wait until the controller has picked up the command.
- The Alarm Center crashed into a render loop from an unstable store selector.

**Tooling**
- Vitest web unit tests (alarm logic, API client). CI now runs `pnpm test`.
- Tests: 66 API, 22 simulator, 10 web.

### Milestone A — Foundations (2026-11-18)
**Security**
- Real authentication: bcrypt password hashes, JWT login (`/auth/login`, `/auth/me`), role checks on every endpoint, and a service token for the simulator. Removed the credentials that were hardcoded in the frontend.
- CORS limited to configured origins. The app refuses to start in production with default secrets.

**Commands & safety**
- New command service: whitelisted types, target/payload validation, role permissions and interlocks (stale state, system mode, zone already active, duplicate, max concurrent zones, zone combinations, pump health, critical tank level).
- Rejected commands are persisted for the audit trail. Stuck commands time out after 15 s. Every step is written to `event_log`.

**Real-time**
- The WebSocket now actually broadcasts: `state.snapshot`, `zone.state.changed`, `pump.state.changed`, `system.mode.changed`, `command.updated` and `telemetry.stale`.
- The web app uses one shared WebSocket connection with a polling fallback and honest LIVE / POLLING / STALE / OFFLINE status.

**Platform**
- First Alembic migration. Tables no longer come from `create_all`.
- Timezone-aware UTC everywhere. Dialect-agnostic state upsert (ready for PostgreSQL).
- Vite dev proxy for `/api` and `/ws`, so the app works from other devices on the LAN.
- The web app now uses `@algaroshy/contracts` types. This exposed a bug: zones were checked against a `"fault"` health value that doesn't exist, so faulted zones were never highlighted.

**Honesty fixes**
- Removed the mock alarms, the fake KPI and moisture trends, the hardcoded soil temperature and the "2 WARNINGS" badge. Labelled the sample chart.
- `/health` no longer claims AI features are enabled.
- "EMERGENCY STOP" in the zone drawer was really a zone stop and is now labelled as one. Added a real global STOP ALL.

**Fixes**
- `pnpm build` and ESLint pass. `run.bat` starts the web app (wrong package filter) and now migrates and seeds first. The seed no longer crashes on Windows consoles. Fixed a simulator signal handler that captured the loop variable.

**Tooling**
- 46 tests (API + simulator), ruff lint/format, and a GitHub Actions CI workflow.

### Added — Phase 1: Domain + Database
- 🗄️ 22 SQLAlchemy models (farm, zones, pumps, valves, sensors, schedules, commands, alarms, cycles, event_log, telemetry, users, 6 AI models)
- 🔧 Pydantic schemas for all entities (response + update)
- 🌐 FastAPI server with CORS, lifespan, versioned routes (`/api/v1`)
- 📡 CRUD endpoints: farm, zones, pumps, valves, sensors (GET + PATCH)
- 🏥 Health check endpoint with AI feature toggle status
- 🗃️ Alembic migration infrastructure (async env.py, config, template)
- 🌾 12-zone seed script (12 zones, 12 valves, 2 pumps, 2 sources, 15 sensors, 1 admin)
- 🤖 AI-ready tables: suggestions, anomalies, weather cache, advisories, insights, maintenance predictions
- 📊 Append-only event log with AI actor support
- 📈 Telemetry time-series table with device state snapshot cache
- 🧠 `docs/AI_FEATURES.md` — 10 AI feature specifications
- AI type definitions in `@algaroshy/contracts` (ai-types.ts)
- 15+ AI enums: AIFeature, AnomalyType, WeatherCondition, VoiceIntent, etc.
- 25+ AI interfaces: AlarmAssistant, WeatherAdvisor, AnomalyDetection, etc.
- AI env configuration: Gemini API, Weather API, feature toggles
- Phase 7 (AI Integration) added to PROJECT_STATUS.md
- Backend deps: google-genai, numpy, apscheduler, jinja2

## [0.1.0] — 2026-04-18

### Added — Phase 0 Complete ✅
- Project documentation pack (16 docs + 2 SVG layouts) in `docs/`
- Root `README.md` with project overview, tech stack, and setup guide
- `.gitignore` for Python + Node.js + React Native monorepo
- `.env.example` environment configuration template
- `CHANGELOG.md` version history tracking
- `CONTRIBUTING.md` contribution guidelines and development workflow
- `PROJECT_STATUS.md` progress tracker for all build phases
- pnpm + Turborepo monorepo (7 workspace packages)
- `@algaroshy/contracts` — shared enums, types, alarm registry, 12-zone seed data
- `apps/api` — FastAPI backend scaffold
- `apps/web` — Vite 8 + React 19 + TypeScript + Tailwind v4.2.2
- `apps/simulator` — Python simulation engine scaffold
- `apps/mobile` — Expo placeholder
- Git initialized, first commit, pushed to GitHub
