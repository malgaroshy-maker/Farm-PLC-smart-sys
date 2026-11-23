# Changelog

All notable changes to the Algaroshy Farm Smart Irrigation System will be documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/).

---

## [Unreleased]

### Milestone F — Satellite map trace (2026-11-23)
- Block 8, third review:
  - trellis rows for enab
  - big mother pomegranate trees for ummahat, larger than the other pomegranates
  - exactly three rows of big old olives for zaytoun_2
  - rows aligned with the strip edges and centred
  - footpaths between the strips
  - names inside the strips
  - close-up drawer art for ummahat and zaytoun_2
- Second review:
  - the middle building is one connected building (barn, brooder, workers' rooms) with Codex-generated roof art
  - the farm rest house (استراحة المزرعة) is inside the boundary
  - the well is underground, drawn as a flush cap north of the control room
  - enab is wider toward ummahat
  - the mixed-fruit strip has almond, lemon and orange trees
  - new sand texture and tyre ruts on the tracks
  - the block 8 strips have always-visible pins
  - the dashboard map is taller (most of the screen on desktop, full width on phones)
- Fixed: the zone drawer refetched its baseline on every live update (`useT` returned a new `t` each render).
- Fixed: the launcher no longer shows Vite's virtual-adapter addresses. Vite's coloured output defeated the old filter.
- The farm map is now traced on Esri World Imagery z17 (owner-approved): north-up, true scale (0.5035 m/unit, viewBox 900×980). The blocks are tilted as on the ground, and every zone is within −8 %..+16 % of its legend. Method and table: `tools/map-geometry/README.md`.
- fruit_mix = blocks 10 + 17. The block 8 strips follow the satellite texture and the legend.
- Trees follow the row bearing and row spacing measured per zone.
- New layers: buildings (chicken house, workers' rooms, house) as labelled footprints, the mixed-fruit strip (trees only), the neighbours' orchards (faded) and the wadi.
- The worker lives at the workers' rooms (S5). Pipes and valves are re-routed along the real tracks and marked guessed.
- Briefing: no invented weather defaults, and the zone count comes from the DB. The route-coverage test works with FastAPI 0.165.

### Milestone F — Map Weather & UI Polish (2026-11-20)
- **Live Weather on the Photoreal Map:**
  - Integrated `WeatherWidget` glass panel into `FarmMap` at top-right above zoom controls with temperature (`<bdi>{temp}°C</bdi>`), meteorological wind arrow pointing towards wind source, wind speed, precipitation probability badge, and condition icons.
  - Hover/tap tooltip displays next 6 hours of forecast; mobile breakpoint (< 640px) automatically collapses to a compact chip with tap-to-expand.
  - Virtual clock synchronization: at $\ge 10\times$ simulation speed, forecast display seamlessly reflects the current virtual farm hour.
  - `WeatherOverlay` canvas: runs high-performance `requestAnimationFrame` raindrops when raining or rain probability $\ge 60\%$, and cloud-shadow tint when `cloud_cover_pct` $\ge 70\%$. Honors `prefers-reduced-motion` with static tint.
  - Collapsible map legend with state persistence in `localStorage` (`farm.legendOpen`), defaulting to collapsed on mobile and open on desktop.
- **UI Polish, Phone Experience & PWA:**
  - Re-architected phone bottom navigation to 4 core items: Dashboard (`/`), Map (`/map`), Alarms (`/alarms`), Schedules (`/schedules`), moving secondary pages to the slide-out hamburger menu.
  - Touch targets guaranteed $\ge 44\text{px}$ and safe-area inset padding applied (`env(safe-area-inset-bottom)`, `env(safe-area-inset-top)`).
  - Floating AI assistant dynamically offsets above the bottom navigation bar on mobile devices.
  - PWA install banner prompt listening to `beforeinstallprompt` with persistent dismissal memory (`farm.installDismissed`).
  - Meta viewport updated with `viewport-fit=cover` and horizontal scrolling eliminated at 375px.
- **AI Panels & Feedback Enhancements:**
  - Added always-visible `ModelBadge` below AI answers across Alarm Assistant, Floating Chat, and Daily Briefing with clean model names (stripping `free/`) or an amber fallback banner when running offline.
  - Dynamic elapsed seconds counter ("جاري التفكير... (٣ ث)" / "Thinking... (3s)") during AI generations.
  - One-click copy-to-clipboard on AI responses with 2-second checkmark feedback.
  - Interactive follow-up suggestion chips in Floating Assistant.
- **Schedules & Reports Improvements:**
  - Vertical now-line on the 24-hour schedule timeline indicating current virtual farm clock position.
  - Disambiguated single-letter Arabic day abbreviations (`ن`, `ث`, `ر`, `خ`, `ج`, `س`, `ح`).
  - Interactive step reordering with `↑ / ↓` controls in program edit drawer.
  - Reports default date range updated to last 7 days (`Africa/Tripoli` time) with sticky table headers and prominent CSV export button.
- **Backend, Security & Ops:**
  - Added `cloud_cover_pct` to `WeatherData` schema, Open-Meteo query parameters, and `WeatherCache` database model with Alembic migration `1b84f3124c4a`.
  - Installed `TokenRedactingFilter` on `uvicorn.access` loggers, preventing query param leakage (`?token=[REDACTED]`).
  - Updated `run.bat reset` to preserve user irrigation programs and steps while purging transient history.
  - Filtered link-local (`169.254.x.x`), VirtualBox (`192.168.56.x`), and Docker bridge (`172.16–31.x.x`) IP addresses from launcher LAN display.
  - Documented satellite georeferencing workflow and bounding box in `tools/map-geometry/README.md`.


### Milestone E review fixes: Explain answers with real AI (2026-11-20)
- **AI tools accept the arguments models naturally send.** `get_schedule`, `get_cycles` and `get_recent_telemetry` take an optional `zone_id`, and `get_forecast` takes `days`. Live, deepseek called `get_schedule(zone_id=…)`; the tool rejected it until its retries ran out, so every "Explain alarm" fell back to rule-based. With the real key, Explain now returns AI answers built from live tool data (17–22 s on the free tier).
- **One retry on the second APInex model** (`muse-spark-1.3`) after a non-transient failure (tool or validation error, provider refusal), before rule-based.
- **Every answer says why it fell back.** `fallback_reason` (`timeout` / `tool_error` / `invalid_output` / `provider_error` / `language_purity` / `error`) is set by the server, never by the model, and the admin call log keeps the detail.
- **No invented weather in the forecast tool.** Missing daily data is now `null` instead of 30 °C / 0 mm / 4.5 mm ET₀.
- "Test connection" uses the provider and model saved in the AI settings page, not only `.env`.
- Regression tests (API 189).

### Milestone E Round 3 — Benchmarking, Arabic Purity & Honest Fallbacks (2026-11-19)
- **AI Model Benchmark Tool (`tools/ai-bench`):**
  - Created maintained CLI benchmark runner `tools/ai-bench/ai_bench.py` and documentation `tools/ai-bench/README.md`.
  - Benchmarks all 23 free APInex models across the 3 core agricultural tasks: Alarm Explanation (ALM-012 no-flow), Tool Calling (`get_zone_state` on Rumman 2), and Weather Advice (85% rain -> skip).
  - Enforces concurrency 2 via `asyncio.Semaphore(2)`. Evaluates pass/fail, latency, and Arabic language purity (scoring foreign scripts: Hangul, CJK, Kana, Cyrillic, and disallowed English words).
  - Safe key management: reads `APINEX_API_KEY` from `.env`, never logs or outputs credentials. Includes `--dry-run` mode for CI simulation.
  - Documented "How to re-run" instructions in `docs/AI_MODELS.md`.
- **Benchmark-Validated Default Model Chain:**
  - Configured default chain: `free/deepseek-v4-pro-0813` (fastest & high accuracy) → `free/muse-spark-1.3` (cleanest Arabic) → direct Gemini (`gemini-2.5-flash`) → rule-based offline engine.
  - Updated `apps/api/app/config.py`, `.env.example`, `models/ai.py`, and created migration `7c4d5e6f7a8b`.
- **Arabic-Purity Guard:**
  - Built `apps/api/app/services/ai/purity.py` checking Arabic outputs for foreign characters and non-whitelisted English words.
  - Impure outputs trigger an automatic fallback retry with the next model in the chain (recording `fallback_reason="language_purity"` in the call log).
- **Model Catalog Metadata & Error Caching:**
  - Added `model_catalog.py` with metadata for all 23 free models: quota multipliers (×2/×3/×5), tools ✓, vision ✓, and verdict badges (recommended / language mixing / subscription-only 402 / no chat 400).
  - Runtime cache records HTTP 400 and 402 failures, marking models unavailable and excluding them from fallback chains.
  - Added `model_used` badge to all AI response DTOs and UI components (Alarm Assistant, Floating Chat, Daily Briefing, Suggestion Cards).
- **Real Endpoints & Elimination of Fake Fallbacks:**
  - Implemented real `POST /api/v1/ai/test` returning genuine measured latency and provider diagnostics (no fake `215ms` success mock).
  - Implemented real `GET /api/v1/ai/baselines/{zone_id}` backed by `apps/api/app/services/anomaly.py` returning genuine median/MAD bands or honest "not enough data yet (N/5 runs)" banners (removed hardcoded `14.2 m³/h` mock).
  - Audited and eliminated fake fallback values across frontend `catch` blocks.
- **Route Coverage & Purity Tests:**
  - Added `test_route_coverage.py` asserting all frontend API client URLs map to real FastAPI endpoints.
  - Added `test_ai_purity.py` and `test_ai_model_catalog.py` unit test suites.

### Milestone E Review Fixes & Live Hardening (2026-11-19)
- **Dependency Packaging & Requirements:**
  - Added `pydantic-ai-slim[openai,google]==2.71.0` and `respx>=0.23.1` to `apps/api/requirements.txt`.
  - Re-installation hash checked by `scripts/start.mjs`; verified `run.bat --smoke` executes cleanly.
- **Session-Per-Tool Concurrency Fix:**
  - Migrated `AIDeps` to carry `session_factory: async_sessionmaker[AsyncSession]`. Each read-only tool acquires and disposes its own session via `async with ctx.deps.session_factory() as db:`.
  - Resolved `concurrent operations are not permitted` while maintaining full parallel tool call execution in Pydantic AI.
  - Added regression test `test_parallel_tools_concurrency_regression` executing all 6 tools concurrently in one turn.
- **Tool Bug Fixes & Schema Alignment:**
  - Corrected `zone.zone_code` to `zone.code` in `get_zone_state`.
  - Fixed `get_schedule` to serialize multi-zone sequential programs and schedules robustly without retry exhaustion.
  - Safe error handling across all 6 live tools returning structured error strings or `ModelRetry` on missing data.
- **APInex Defaults & Timeouts:**
  - Corrected APInex gateway to `https://api.apinex.bond/v1`.
  - Configured owner-selected free defaults: primary `free/gemini-3.8-flash`, secondary fallback `free/glm-5.3-flash`. Removed all legacy `gpt-4o-mini` strings.
  - Per-feature timeouts: 45 s for explain/chat, 90 s for background advisor/briefing. Applied `UsageLimits(request_limit=5)`.
- **Persistent Admin AI Settings:**
  - Created Alembic migration `6b3c4d5e6f7a` adding `ai_settings` table.
  - Added `PUT /api/v1/ai/settings` allowing admins to dynamically change provider order, select model per feature from runtime APInex `/v1/models`, and toggle features.
  - Built agent fallback models dynamically per request from DB settings without API restarts.
  - Frontend [AiSettings.tsx](apps/web/src/pages/AiSettings.tsx) provides editable form controls, model selection dropdowns, key status indicators, connection test button, and last 20 AI calls table.
- **Dynamic Farm-Context Injection:**
  - Replaced hard-coded crop lists with dynamic database query `build_farm_context_block()` querying real zone names, crops, and live states.
- **Fallback Visibility & Health Reporting:**
  - In-memory ring buffer tracking last 20 AI calls with feature, provider, model, latency, and fallback reason.
  - `/health` reports `ai: degraded` when the primary provider fails and falls back.
  - Frontend drawers show progress states ("جارٍ التحليل والتشخيص…"), latency, and cancel buttons (`AbortController`).
- **Test Isolation & Rate Limiting:**
  - Isolated test suite in `conftest.py` with `ALLOW_MODEL_REQUESTS = False` and blanked API keys.
  - Added per-user sliding window rate limiting (30 requests/min) on AI endpoints.


### Milestone E — Artificial Intelligence Intelligence (2026-11-19)
- **Multi-Tier AI Provider Fallback Chain:**
  - Built with Pydantic AI (`pydantic-ai-slim[openai,google]>=2.71.0`) utilizing `FallbackModel`.
  - Tier 1: Primary APInex gateway (`OpenAIChatModel` with `OpenAIProvider`, `free/gemini-3.8-flash`).
  - Tier 2: Direct Google Gemini (`GoogleModel` with `GoogleProvider`).
  - Tier 3: Deterministic rule-based offline fallback service (`RuleBasedService`).
  - 15-second timeouts, exponential backoff on 429/5xx, in-memory SHA-256 request caching.
  - Dynamic model discovery from APInex `GET /v1/models` with in-memory TTL caching.
  - Strict payload sanitization pipeline (`redaction.py`) stripping IPv4/IPv6, emails, Bearer/JWT tokens, API keys, passwords, and operator names before LLM submission.
  - Read-only farm tools taking `RunContext[AIDeps]` (`get_alarm`, `get_zone_state`, `get_recent_telemetry`, `get_cycles`, `get_schedule`, `get_forecast`); zero write or command tools.
- **Alarm Assistant (Bilingual AR/EN):**
  - Endpoints `POST /api/v1/ai/explain-alarm` and `POST /api/v1/ai/chat`.
  - Generates structured `AlarmExplanation` with summary, likely causes, step-by-step actions, safety notes, confidence score, and provider label.
  - "Explain / اشرح" button on every alarm row in Alarm Center and Zone Drawer opening side panel.
  - Persistent floating assistant action button on all pages expanding into a slide-over chat drawer with live telemetry badges (pressure, flow, pumps, zones) and quick prompt pills.
- **Weather-Aware Irrigation Advisor:**
  - Open-Meteo weather integration targeting exact farm coordinates (`32.516250, 14.070361`, Africa/Tripoli) with 3-hour caching and ET0 evapotranspiration extraction.
  - Deterministic evaluation of upcoming 24h programs: rain skip ($\ge 50\%$ or $\ge 2\text{ mm}$), heat extension ($\ge 38^\circ\text{C}$ or $\text{ET}_0 \ge 7\text{ mm}$ $\rightarrow +20\%$), and safe no-forecast fallback.
  - Suggestion cards on Dashboard and Schedules page with duotone FarmIcons.
  - One-tap approve with 5-second undo toast (Operator+ permission) creating single-day `ProgramOverride` in database; scheduler honors override once and marks applied.
- **Statistical Anomaly Detection (No LLM):**
  - Pure statistical engine (`apps/api/app/services/anomaly.py`) computing median + MAD / robust z-scores per zone from completed cycles ($N \ge 3$).
  - Detects mainline leaks (high flow + low pressure) raising S2 alarm `ALM-046` (*"Possible leak / تسريب محتمل في الخط الرئيسي"*).
  - Detects clogged emitters (low flow + high pressure) raising S2 alarm `ALM-047` (*"Possible clogged emitters / انسداد محتمل في النقاطات"*).
  - 15-second valve travel grace period and 10-second debounce.
  - Added baseline visualization section in Zone Drawer showing normal flow and pressure bands.
- **Daily Morning Briefing:**
  - Automated daily briefing synthesized at 06:00 farm time (`clock.farm_now()`) summarizing yesterday's water consumption, cycle count and outcomes, tripped alarms, anomalies, and today's forecast.
  - Stored in `ai_briefings` table (`GET /api/v1/ai/briefing?date=YYYY-MM-DD`).
  - Collapsible top hero card on main dashboard and mobile status screen.
- **Admin AI Settings & Ops:**
  - Dedicated admin page at `/settings/ai` for provider ordering, feature model configuration, global and per-feature toggles, live connection testing with latency display, key status, and farm coordinates.
  - `/health` endpoint updated reporting live `ai` (`ok`, `degraded`, `off`, `not_configured`) and `weather` (`ok`, `stale`, `off`) health.
- **Database & Migrations:**
  - Created Alembic migration `5a2b3c4d5e6f` adding `ai_briefings`, `program_overrides`, and weather cache columns. Verified on fresh DB and `farm.db`.
- **Verification:**
  - 166 API tests passed (`pytest apps/api/tests`).
  - 59 Web tests passed (`vitest run`).
  - ESLint passed with 0 errors/warnings.
  - Vite production build passed with zero chunk size warnings.
  - All 15 simulator scenarios verified including mainline leak scenario triggering ALM-046.


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
