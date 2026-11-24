# 📊 Project Status — Algaroshy Farm Smart Irrigation System

**Last Updated:** 2026-11-23
**Current milestone:** A ✅ · B ✅ · C ✅ · D ✅ · E ✅ · F ✅ (satellite map, weather, UI polish) → **Milestone G** in progress (G1 performance & reliability ✅ · G2 AI ✅ · G3 extensibility ✅ · G4 UI polish ✅ · G6 docs ✅ · hardware research ✅ · G7 field readiness ✅ (owner review pending) · G5 PLC design next): hardening, AI, polish, PLC design, hardware research, demo video ([plan](docs/MILESTONE_G_PLAN.md))
**Roadmap:** [docs/AUDIT_AND_ROADMAP.md](docs/AUDIT_AND_ROADMAP.md)

> This file only marks something ✅ when it works end-to-end and has tests or was verified in the running app.
> The earlier version of this file over-claimed Phases 1–3. See the audit for what was wrong.

---

## What works today (verified)

| Area | Status | Notes |
|------|--------|-------|
| Monorepo, contracts, docs | ✅ | pnpm + Turborepo. `@algaroshy/contracts` is used by the web app as the single source of types. |
| Database + migrations | ✅ | 26 SQLAlchemy models (including `FarmClockModel`, `Program`, `ProgramStep`, `SchedulerState`, `IrrigationCycle`). Alembic migrations up to head (`4e1f8d2a3c5b` adding `water_is_estimate`). `alembic check` clean. Fresh DB upgrade verified. |
| Seed data | ✅ | Starting point only; the owner edits zones in Settings. 12 zones, 12 valves, 2 pumps, 2 sources, 15 sensors, admin user with a bcrypt-hashed password. |
| Auth | ✅ | `POST /auth/login` (JWT), `GET /auth/me`. Roles owner_admin / operator / viewer enforced on every endpoint. Operator+ can toggle schedules; Admin creates/edits/deletes. The simulator uses a service token. |
| Virtual Farm Clock | ✅ | Single source of truth in API (`app/core/clock.py`), persisted, monotonic. Live speed control (pause, 1×, 10×, 60×, 360×), jump to time (presets + custom HH:MM), step (+1 min), WS `clock.changed` broadcasts, amber SIMULATED TIME badge (`#ff9f43`) with speed in AR+EN, presenter header chip (desktop) collapsing to badge on mobile, full Simulator page panel, and "Back to real time" with reset confirmation. Telemetry, event times, alarm windows, and map lighting/season follow farm time; link staleness and command timeouts stay on real wall clock. Locked to real time unless `CONTROLLER_MODE=simulator`. |
| Sequential Programs & Schedules | ✅ | Sequential irrigation programs (`/api/v1/schedules`). Strict conflict checker verifies 24 h total runtime, zone max runtimes, weekday overlaps across midnight and week boundaries, forbidden zone combinations, and pump concurrency. 24 h weekly timeline UI with interactive edit drawer, crop icons, live conflict validation, and save confirmation. Next irrigation card ticking on simulation clock on dashboard and mobile status row. |
| Scheduler Service | ✅ | Virtual farm-clock scheduler (`app/services/scheduler.py`). Driven by monitor tick on `clock.farm_now()`. Persists last-fired timestamps across restarts (`scheduler_state` table). Dispatches commands exclusively through `submit_command` with `actor_type="scheduler"`, enforcing all physical and hydraulic interlocks. Sequential step transitions wait for zone idle. Handles pause, speed changes, backward/forward jumps without double-firing or mass-firing. On blocked start (interlock rejection), records skipped cycle, raises S1 info alarm (ALM-035), and seamlessly advances to next step. |
| Irrigation Cycle Log | ✅ | Comprehensive run audit (`/api/v1/cycles`). Logs all runs (manual, scheduled, scenario). Tracks planned/actual start, end, duration in farm time, initiator, speed-aware trapezoidal water volume integration from `zone.flow_m3h` telemetry, outcome (`completed`, `aborted`, `faulted`, `manual_stop`, `skipped`), and linked alarm codes. Exposed in Zone drawer history and feeds water accounting. |
| Reports & CSV Export | ✅ | Tabbed reports page (`/reports`): Daily irrigation, Water per zone, Pump runtime, and Alarm history. Date range selector in Tripoli local time, Recharts visual charts, clean data tables, empty states, and one-click CSV export with UTF-8 BOM (`\xef\xbb\xbf`) and bilingual Arabic/English headers for Excel compatibility. |
| Command service | ✅ | Whitelisted command types, target and payload validation, role permissions, interlocks (stale state, system mode, already running, duplicate, max concurrent zones, zone combinations, pump health, low tank, **open critical alarm**). Rejected commands are kept for the audit trail. Real-time command timeout tracking (`requested_at_real`). A stop supersedes open starts. Every step goes to `event_log`. |
| Real-time | ✅ | `/ws?token=` sends `state.snapshot` on connect (with `farm_now` and `speed`), then `zone.state.changed`, `pump.state.changed`, `system.mode.changed`, `command.updated`, `telemetry.stale`, `clock.changed`, `schedule.fired`, `schedule.skipped`, `schedule.missed`, `program.started`, `program.finished`, `cycle.started`, `cycle.completed`, `cycle.skipped`, `cycle.aborted`. The web app uses one shared connection and falls back to polling. |
| Simulator | ✅ | Plays the PLC and the farm. Follows API clock dynamically via WS. Physics `dt = real_dt × speed` with sub-stepping; pause suspends physics while publishing; jumps stop active zones and apply closed-form soil drying and tank balance. Protection for pump trip/failed start, valve stuck closed/open, no flow, leak, critical tank, e-stop and sensor fault. **Hydraulic constants are placeholders until the site survey.** |
| Alarm engine | ✅ | 20 codes from ALARM_MATRIX with AR/EN guidance, kept in sync with contracts by a test. Lifecycle ack → latched → reset → history. A "maintenance done" sign-off clears repeated-fault alarm (ALM-036). 24 h window follows farm time; debounce timers and staleness checks follow real wall-clock time. |
| Scenarios | ✅ | 15 scripted scenarios (SIMULATION_PLAN §5), run through normal command path. Includes `scheduled_day` (3 zones at 60×) and `scheduled_blocked_start` (low tank interlock skipping). Run from Simulator page or `/sim/scenarios`. |
| Telemetry history | ✅ | Persisted every 10 s farm time, at most 1/s real, farm timestamps, retention in farm time. `/telemetry/series` and `/telemetry/water-today` drive zone and dashboard charts. |
| Farm map | ✅ | **Traced from Esri satellite imagery (z17), north-up**, 0.5035 m per map unit (`tools/map-geometry/satellite_retrace.py`); the owner's sketch is kept as an area cross-check. Owner-confirmed layout: block 8 strips (rumman ummahat with big mother trees, enab trellis rows, zaytoun_2 as three rows of big old olives), mixed-fruit strip (almond, lemon, orange; not irrigated), one connected building (barn, brooder, workers' rooms), the farm rest house inside the boundary, and the underground well just north of the control room. Thousands of individual trees at real row spacing, fruit following the season. Fly-to on zone select and on new S2/S3 alarms, alarm rings, farm-life sprites (tractor, birds, worker), buried mainline + laterals, tank, booster, control room. Animations follow flow and farm-local day/night; each can be switched off in Settings. |
| Arabic-first UI | ✅ | Arabic by default with full RTL and an English toggle. Bundled IBM Plex Sans Arabic font (works offline). Logo + مزرعة الجروشي branding. Farm-local clock. Numbers stay Western digits. |
| Pages | ✅ | Dashboard, Zones, Equipment, Alarm Center, Event log, Schedules, Reports, Settings (Features · Notifications · Zones & equipment · AI · Backups), Help (operator guide), Simulator (admin-only, behind **presenter mode**). Every page has loading, empty (illustrated) and error-with-retry states. |
| Start script | ✅ | `run.bat` / `run.sh` (dev) and `run.bat demo` (phones + PWA). One window, first-run self-setup, a single `API_PORT`, clean Ctrl+C shutdown, `stop.bat` safety net, `--smoke` self-test. `run.bat reset` clears operating history for a clean demo (keeps users and settings). |
| Phone / PWA | ✅ | Responsive layout with bottom navigation and a slide-in menu. Installable (manifest, icons, service worker that never caches `/api` or `/ws`). |
| Web MVP | ✅ | Real login, live map (incl. starting/stopping state), dashboard side column (tank, pumps, alarms, trends, water today, next irrigation), zone panel with a duration picker + confirm and real cycle history, start/stop with interlock feedback, alarm chime + mute, reduce-motion toggle, global STOP ALL, Alarm Center (active/history, ack/reset, AR/EN guidance), Simulator page with Virtual Farm Clock panel, Schedules page with 24h timeline and drawer, Reports page with charts and CSV export, honest connection status. |
| AI Services & Assistant | ✅ | Pydantic AI agent with a fallback chain: APInex primary (`free/deepseek-v4-pro-0813`), APInex backup (`free/minimax-m3.1-flash`, re-tested 2026-11-23; see [AI_MODELS](docs/AI_MODELS.md)), Google Gemini, then deterministic rule-based answers. A live farm snapshot goes into every prompt; chat answers in two steps (fast answer, then tools only when history is needed). Arabic normalizer (Western digits) and purity guard with an allow-list of real farm names. Advisor decisions are made by server rules; the AI only explains them, with a "why?" panel. Every call is logged (`ai_call_log`, `/ai/usage`). Explain on every alarm, floating assistant, AI settings tab, baselines per zone. |
| Weather & Irrigation Advisor | ✅ | Open-Meteo weather client targeting exact farm coordinates (`32.516250, 14.070361`, Africa/Tripoli) with 3-hour caching and ET0 evapotranspiration extraction. Deterministic advisor rules: rain skip ($\ge 50\%$ or $\ge 2\text{ mm}$), heat extension ($\ge 38^\circ\text{C}$ or $\text{ET}_0 \ge 7\text{ mm}$ $\rightarrow +20\%$), and safe offline fallback. Suggestion cards with one-tap approve (5-second undo toast) creating single-day program run overrides honored by scheduler. |
| Statistical Anomaly Detection | ✅ | Non-LLM statistical anomaly detection engine (`apps/api/app/services/anomaly.py`) computing median + MAD / robust z-score baselines per zone from completed cycles ($N \ge 3$). Evaluates live flow and pressure during irrigation: high flow + low pressure triggers S2 alarm ALM-046 (Possible leak); low flow + high pressure triggers S2 alarm ALM-047 (Possible clogged emitters). Debounce and valve-travel grace periods eliminate false positives. Baseline band visualized in Zone Drawer. |
| Daily Morning Briefing | ✅ | Automated daily briefing synthesized at 06:00 farm time (`clock.farm_now()`). Summarizes yesterday's water consumption, cycle count and outcomes, tripped alarms, anomalies, and today's forecast. Stored in `ai_briefings` table; surfaced as collapsible top hero card on main dashboard and mobile status screen. |
| Weather on Map & UI Polish | ✅ | Glass weather widget (temp, meteorological wind arrow, rain %, 6h hourly forecast tooltip), dynamic rain and cloud-shadow canvas overlays, collapsible legend with persistence. 4-item phone bottom nav (Dashboard, Map, Alarms, Schedules) with $\ge 44\text{px}$ targets, safe-area insets, always-visible AI model badge, elapsed query seconds timer, copy button, friendly rule-based banner, 7-day default reports range with sticky headers and CSV export, PWA install prompt. WS token redaction in logs, launcher LAN IP filter, preserved programs in demo reset. |
| Performance & health | ✅ | Shared polling paused when the tab is hidden, SQLite WAL, composite telemetry index, SQL-bucketed chart series (about 80 ms), downsampling of old telemetry. `/system/health` drives a health badge (green/amber/red) with a plain-language panel. |
| Feature switches | ✅ | Owner switches for each AI feature, map effects, automation (schedules, daily weather check, anomaly detection) and alert channels (`/system/features`); changes reach every screen live. |
| Notifications | ✅ | S3 critical and S2 major alarms and the morning briefing go to Telegram and phone push (web push with VAPID), with a test-message button in Settings. Phone push needs HTTPS, so it works on localhost until hosting is decided. |
| Controller adapter | ✅ | The gateway drives a `ControllerAdapter`: the simulator today, and an OPC UA adapter (S7-1500, seq/ack handshake) tested against an in-process OPC UA server, and a Modbus TCP adapter (G7) tested against a built-in register server. PLCSIM Advanced validation comes in G5. See [CONTROLLER_ADAPTER](docs/CONTROLLER_ADAPTER.md). |
| Field readiness (G7) | ✅ | Manual mode (panel switches, hand icon, banner, ALM-042), unexpected flow (ALM-021), power cut with the 30-minute resume rule (ALM-033), fallback program, pump health (kW, current, well level, filter, ALM-027/039), soil moisture with per-crop levels and soil logic (levels proposed until the owner confirms). Shown in the simulator; the PLC side is G5. |
| Farm server & backups | ✅ | `start.mjs server` (headless, restarts crashed parts), Windows/Linux service installers, daily backups (local, USB, Google Drive via rclone) with restore on restart in Settings → Backups, Tailscale HTTPS guide ([FARM_SERVER](docs/FARM_SERVER.md)). The installers have not been run on the farm PC yet. |
| Operator guide | ✅ | Arabic + English guide in two parts (daily operation, administration): in-app Help page, [docs/OPERATOR_GUIDE.md](docs/OPERATOR_GUIDE.md) and a printable A4 PDF. |
| Tests + CI | ✅ | 250 API + 41 simulator + 107 web + 7 map-model + 11 launcher tests (416 total). GitHub Actions: ruff, pytest, migrations, eslint, typecheck, build, vitest. |

## Live scenario suite (2026-11-19)

All **15/15** scenarios pass against the running API + simulator (timescale 1× and 60×): normal cycle, direct-well cycle, tank critical during a run, booster failed start, pump trip mid-cycle, valve failed open, no flow, valve failed close, mainline leak (verifying ALM-046 anomaly trigger), emergency stop, comms loss, repeated fault, reset farm, scheduled day (3 sequential zones with water > 0), scheduled blocked start (low tank interlock skip + S1 alarm + continuation).

## Known gaps (not done — don't demo these as real)

| Gap | Planned in |
|-----|-----------|
| PLC program and PLCSIM Advanced test (the adapter skeleton exists) | G5 |
| Phone push on phones needs HTTPS: Tailscale `serve` is documented but not set up yet | Farm PC setup |
| PostgreSQL in production, SMS/escalation | Production track |
| Per-crop soil levels are proposed values; soil logic waits for the owner to confirm them | Owner input |
| Farm total area: the satellite trace gives 9.97 ha, the seed says 11.9 ha | Owner input |
| Scenario suite runs manually against a live stack, not in CI | CI improvement |
| Pipe routes are a plausible guess. Edit `tools/map-geometry/network.py` with the real routes | Owner input |
| Dual-zone operation (`MAX_CONCURRENT_ZONES>1`) is supported by interlocks but not exercised by any scenario | After commissioning |

## Milestones

| Milestone | Status |
|-----------|--------|
| **A: Foundations** | ✅ Done 2026-11-18 |
| **B: Credible simulator + real alarms** | ✅ Done 2026-11-18 |
| **C: Demo-quality UI + PWA** | ✅ Done 2026-11-18 |
| **D: Simulation time, schedules, cycles, reports** | ✅ Done 2026-11-19 |
| **E: AI (alarm assistant, weather advisor, anomaly detection, daily briefing)** | ✅ Done 2026-11-19 |
| **F: Map weather & UI polish, satellite map** | ✅ Done 2026-11-23 |
| **G: Hardening, AI, polish, PLC design, research, demo video** | 🔄 G1–G4, G6, G7 and the hardware research done; G5 next ([plan](docs/MILESTONE_G_PLAN.md)) |
| Production track (PLC adapter, hosting, hardening) | ⬜ After the demo |

## Decisions

| Item | Status |
|------|--------|
| Zones | ✅ 12 to start; the owner adds, edits or disables zones in Settings |
| Mobile | ✅ PWA from the web app (no separate React Native app) |
| Order | ✅ Foundations → demo polish → production |
| PLC model / protocol | ✅ **Siemens S7-1200/1500 via OPC UA** (owner, 2026-11-20). G5 designs on an S7-1500 with TIA Portal V19 + PLCSIM Advanced; the hardware research report picks the final CPU. Test on PLCSIM Advanced before hardware. The adapter interface stays protocol-neutral so the simulator remains an implementation. |
| Hosting | ❓ Not decided. Comes after the demo. |
| Pump specs, valve sizes, pipe diameters | ❓ Need a site survey (affects simulator constants and thresholds) |
