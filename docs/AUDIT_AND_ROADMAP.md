# Audit & Roadmap — Algaroshy Farm Smart Irrigation

**Audit date:** 2026-11-18 · **Audited commit:** `0a6c2be` (master)

**Decisions taken for this roadmap:**
- PLC model: not decided. Keep the adapter protocol-neutral.
- Hosting: not decided. Build the **simulation demo** first; production comes later.
- Mobile: **PWA** built from the web app (no separate React Native app).
- Order: **fix the foundations first**, then make the demo polished.

---

## 1. Honest assessment

### What's good
- **The documentation is very good.** About 3,000 lines across PRD, alarm matrix (50 codes), IO list, PLC logic, domain model and test plan. Most projects never get a spec this clear, and it's the project's biggest asset.
- **Sensible architecture.** Local-first, the PLC as the safety authority, simulation-first development, and "AI suggests, humans decide" are the right principles for irrigation control.
- **Shared contracts package** (`packages/contracts`) holds enums, types, alarm definitions and seeds for all 12 real zones.
- **Clean backend skeleton.** FastAPI with async SQLAlchemy, a versioned `/api/v1`, and 22 models that map well to the schema doc.
- **The web UI looks good.** The dark HMI style, zoomable map with Arabic zone labels and zone drawer make a strong first impression.

### What's wrong (the hard truth)
The code is about **2,100 lines of scaffold**, but `PROJECT_STATUS.md` marks Phases 1–3 as ✅ DONE. Several of those "done" items don't work or are fake. Anyone (an investor, a client, or you in 3 months) who trusts the status file will be misled. **The status file has to be corrected.**

| # | Claimed | Reality | Evidence |
|---|---------|---------|----------|
| 1 | WebSocket event emitter ✅ | **Dead code.** `manager.broadcast()` is never called. The web app polls `/state/map` every second. | `apps/api/app/routers/websocket.py` |
| 2 | Alarm center with Ack/Reset ✅ | **Mock data.** 4 hardcoded alarms. The Ack/Reset buttons have no handlers. There's no alarm API and no alarm engine. `active_alarms` is always `[]`. | `apps/web/src/pages/AlarmCenter.tsx`, `routers/state.py` |
| 3 | Login / auth ✅ | **Credentials are hardcoded in the frontend JS** (`Mahamed97`/`Admin1234`, readable by anyone who opens devtools). "Auth" is a `localStorage` flag. The API has **zero auth**: anyone on the network can start or stop pumps. | `pages/Login.tsx`, every router |
| 4 | Fault injection ✅ | **Valve faults always fail.** The simulator never loads valves or sensors (`fetch_initial_layout` only loads zones and pumps). A pump trip doesn't stop the zone, which keeps "running" at 5 m³/h with 0 bar. | `simulator/src/client.py`, `engine.py` |
| 5 | Command handling ✅ | **No validation or interlocks.** `POST /commands` accepts any `command_type` and target (verified: `delete_everything` → 200). No max-concurrent-zones check, no combination check, no event-log entry, no actor. | `routers/commands.py` |
| 6 | Scenario runner ✅ | Doesn't exist. `scenarios.py` only contains `FaultInjector`. | |
| 7 | Alembic migrations ✅ | `versions/` is empty. Tables come from `create_all` in dev only. | `alembic/versions/` |
| 8 | Zone drawer with charts ✅ | The chart is **mock data**. Soil temp is hardcoded to `24`, the trend to `-12%`, and the flow KPI trend to `4.2%`. The header always shows "2 WARNINGS" and "SYS.ONLINE". | `ZoneDrawer.tsx`, `Dashboard.tsx`, `DashboardLayout.tsx` |
| 9 | Build ✅ | **`pnpm build` fails** with TS6133 (unused `Activity` import). ESLint reports 6 errors. | `apps/web` |
| 10 | `run.bat` | `pnpm --filter web` doesn't match the package name `@algaroshy/web`, so the frontend won't start from the script. | `run.bat` |
| 11 | Tests / CI | **None.** No test file in the repo. | |
| 12 | 10 AI features | Only docs, types and env toggles exist. `/health` reports AI features as "enabled" even though none are implemented. | `routers/health.py` |

### Other technical issues
- **Simulator physics is a placeholder.** Every state change happens instantly in one tick (no valve travel time, no flow validation). Moisture never dries out. The tank never refills. Any number of zones can run on any pump. "completed" zones stay completed forever.
- **The command path is DB polling.** UI → DB row → simulator polls every 1 s → simulator PATCHes back. That's fine for now, but there's no command timeout, so a command stuck in `pending` stays there forever.
- **`state.py` uses an SQLite-only upsert** (`sqlite.insert`), so it breaks on PostgreSQL.
- **`datetime.utcnow()`** (deprecated, naive) is mixed with timezone-aware columns. Freshness math will bite later.
- **Hardcoded `http://127.0.0.1:8000`** in the frontend means it won't work from a phone or another PC on the LAN, which is the whole point of the PWA.
- **The web app doesn't use `@algaroshy/contracts` at all.** Types are redefined by hand with `any`. Contracts and the backend have already drifted.
- **`CORS allow_origins=["*"]` combined with `allow_credentials=True`** is invalid per the CORS spec and unsafe.
- **No RTL/Arabic UI** despite the "Arabic-first" principle. UI text is English only, and only the zone names are Arabic.
- **The map zone positions are hand-estimated percentages** over a raster SVG. They're fragile and don't scale to the real geometry.
- **The README is stale.** It says Phase 1 is pending and refers to `seed.py`, `main:app` and `run_simulator.py`, none of which match the real paths.

### Verdict
Good vision and a good spec, with a fast prototype on top of it. The prototype is a **UI mockup wired to a toy simulator**, not a working control system yet. That's normal at this stage. The problem is only that the status file says otherwise. Everything here is fixable, and the foundations (models, contracts, layout) are worth keeping. **Don't restart, harden.**

---

## 2. Roadmap

Each milestone ends in something you can run and show. Estimates assume one developer working with AI assistance.

### Milestone A — Foundations ✅ done 2026-11-18
*All items below are done except web unit tests (Vitest), which move to Milestone B. CI covers web lint, typecheck and build.*

1. **Honest status.** Rewrite `PROJECT_STATUS.md` and `README.md` to match reality. Fix `run.bat`. Make `pnpm build` and lint pass.
2. **Real auth.** Add `/auth/login` with bcrypt hashes and JWT. Seed the admin user with a password from `.env`. Add roles (owner_admin / operator / viewer) enforced on every write endpoint. Simulator gets a service token. Remove the hardcoded credentials from the frontend.
3. **Command service.** Whitelist command types from contracts and validate targets. Run interlock checks *before* queueing: zone enabled, max concurrent zones, combination rules, pump available, system mode allows manual. Add command timeout/expiry. Write every command to `event_log` with an actor.
4. **Real-time push.** Have the API broadcast over WebSocket when the simulator syncs (diff-based events from `REALTIME_EVENTS.md`). The frontend uses the WS with a polling fallback. Show connection state honestly.
5. **Config.** Add `VITE_API_URL` and derive the WS URL from it. Fix CORS to explicit origins. Use timezone-aware UTC everywhere. Add a dialect-agnostic upsert.
6. **Contracts as the source of truth.** The web app imports types from `@algaroshy/contracts`. Generate or validate Python enums against them (or generate TS from the FastAPI OpenAPI schema; pick one direction).
7. **Migrations.** Create the first Alembic revision and stop relying on `create_all`.
8. **Tests and CI.** Add pytest for the command service, interlocks and auth; one simulator scenario test; Vitest smoke for the web app. Add a GitHub Actions workflow running lint, typecheck, tests and build.

### Milestone B — Credible simulator + real alarms ✅ done 2026-11-18
*Done as planned, with two changes. The scenario runner lives in the backend: it runs from the Simulator page or the API, not a CLI, so interlocks and the audit trail apply. Web unit tests (Vitest) carried over from A are added.*

1. **Simulator loads everything** from the API: valves, sensors, sources, combinations.
2. **Timed state machine per `PLC_CONTROL_LOGIC.md`:** off → requested → starting_pump → opening_valve (with travel time) → validating_flow → running → stopping → off. Add max runtime and completion at `default_duration_min`.
3. **Physics.** Pump curve (pressure falls as more zones open), per-zone flow from `flow_min/max`, tank drain/refill from the well pump, moisture rising while irrigating and drying out over time (faster at midday), sensor noise. Seeded RNG keeps runs deterministic.
4. **Faults with real consequences.** Valve stuck closed (no flow, triggering a validation alarm), pump trip (zones stop), mainline leak (pressure drop with high flow), sensor stale/out-of-range, low tank (blocks starts).
5. **Alarm engine (backend).** Evaluate live state against the `ALARM_MATRIX.md` rules for the ~15 alarms that matter in the demo. Implement the lifecycle active_unacked → acked → cleared → reset, debounce, and correlation. Add `GET /alarms`, `POST /alarms/{id}/ack` and `/reset`, broadcast over WS, and record in the event log.
6. **Scenario runner.** Scripted scenarios (`normal_cycle`, `pump_trip_mid_cycle`, `leak`, `low_tank`) runnable from the CLI and from an admin panel in the UI. These are what you show in a demo.
7. **Telemetry history.** Store downsampled telemetry points so the charts show real data.

### Milestone C — Demo-quality UI + PWA ✅ done 2026-11-18
*Built to design/DESIGN_BRIEF.md (decided with the owner). Zone polygons come from the traced sketch rather than `geometry_ref`. Pipe routes are a plausible first version for the owner to correct.*

1. **Remove every mock and hardcoded value.** Charts use the telemetry API. Header alarm counts and status are live.
2. **Arabic/English toggle with full RTL layout** (i18n, Arabic font such as IBM Plex Sans Arabic or Cairo). Arabic is the default.
3. **Better map.** Draw zones as real SVG polygons from `geometry_ref` instead of floating boxes, and animate flow along the pipes when a zone runs. Show pump and tank widgets on the map.
4. **Pages:** Alarm center (real, with ack/reset and guidance in AR/EN), Zones list, Event log/audit, Equipment (pumps, valves, sensors), Settings (zones, users), Simulator control panel (scenarios, fault injection, time scale).
5. **Separate global Emergency Stop and per-zone Stop.** Today the button labelled "EMERGENCY STOP" is just a zone stop. Add confirmation dialogs for control actions.
6. **Responsive layout + PWA** (manifest, service worker, installable, offline shell). Test at phone width, which covers the Android goal.
7. **Polish pass:** loading/empty/error states, stale-data banner, toasts for command results.

### Milestone D — Simulation time, schedules, cycles, reports (≈2 weeks)
0. ✅ **Simulation time (Done 2026-11-19)** (spec: [SIMULATION_TIME.md](SIMULATION_TIME.md), decided with the owner 2026-11-19). One virtual farm clock shared by the API, simulator and UI. Live speed control in presenter mode (pause, 1×, 10×, 60×, 360×), jump to a time of day, step (+1 min), an amber SIMULATED TIME badge with speed, and "Back to real time" (which clears demo history). Locked to real time with a real PLC. Schedules (1–2) are built on this clock.
1. Schedule CRUD with a conflict checker (overlap, combinations, pump capacity).
2. Scheduler service (APScheduler) that issues commands through the same command service, so the same interlocks apply.
3. An irrigation cycle log for each run: planned vs actual duration, water used, outcome, alarms.
4. Reports: daily irrigation, water usage per zone, pump runtime, alarm history. CSV export; PDF later.

### Milestone E — AI that earns its place (≈1.5–2 weeks)
Ship **3 features well**, not 10 on paper. Each one must work without the AI service (rule-based fallback) and must only *suggest*:
1. **Alarm assistant.** Explains an alarm in AR/EN using the alarm matrix and live context (Gemini or Claude, behind a provider interface).
2. **Weather-aware advisor.** Uses a forecast API and suggests skip/shorten/delay for scheduled cycles. The operator approves.
3. **Anomaly detection.** Statistical (z-score on flow and pressure per zone), not an LLM. Catches leaks and clogged emitters, and the simulator's leak scenario proves it works.
4. **Daily briefing:** a summary of the cycle log and alarms (cheap to add once 1–3 exist).

Crop vision, voice and seasonal learning stay **deferred** until there's real hardware and data. Remove them from "enabled" toggles until then.

### Later — Production track (after the demo)
- **PLC adapter interface** (`read_tags()`, `write_command()`, `health()`), with the simulator as the first implementation. Then OPC UA (Siemens S7-1200/1500) or Modbus TCP once the PLC is chosen. Validate against PLCSIM Advanced before touching hardware.
- **Hosting decision:** a local edge PC with VPN, or local plus a cloud mirror. Then Docker Compose, PostgreSQL, backups, HTTPS.
- **Security hardening:** rate limiting, audit review, secrets management, and a rule that the cloud can never bypass PLC interlocks.
- **Notifications:** web push (PWA), then SMS through a GSM gateway for critical alarms, plus escalation.
- **Site survey data** (pump specs, valve sizes, pipe diameters) to replace the simulator's guessed constants.

---

## 3. Demo definition of done
A 10-minute demo where you:
1. Log in (real auth) in Arabic and switch to English.
2. See all 12 zones live on the map, with pumps, tank and pressure moving realistically.
3. Start a zone and watch it go through starting → validating flow → running, with water animating on the map.
4. Try to start a conflicting zone and see the interlock reject it with a clear reason.
5. Inject a pump trip: the zone stops, a critical alarm appears instantly over WS, the AI explains it in Arabic, and you acknowledge and reset it.
6. Run the leak scenario: anomaly detection flags it.
7. Show a weekly schedule, a weather suggestion to skip tomorrow's cycle, and the water usage report.
8. Open the same thing on an Android phone as an installed PWA.

**Total estimate to demo-ready: about 7–9 weeks** of focused work (A+B+C ≈ 4–5 weeks gives a strong demo even without D and E).
