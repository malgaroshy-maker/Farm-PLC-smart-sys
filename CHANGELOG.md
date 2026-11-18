# Changelog

All notable changes to the Algaroshy Farm Smart Irrigation System will be documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/).

---

## [Unreleased]

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
