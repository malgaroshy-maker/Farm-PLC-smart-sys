# 📊 Project Status — Algaroshy Farm Smart Irrigation System

**Last Updated:** 2026-11-18
**Current milestone:** A ✅ · B ✅ · C ✅ → next is **D: schedules, cycles, reports**
**Roadmap:** [docs/AUDIT_AND_ROADMAP.md](docs/AUDIT_AND_ROADMAP.md)

> This file only marks something ✅ when it works end-to-end and has tests or was verified in the running app.
> The earlier version of this file over-claimed Phases 1–3. See the audit for what was wrong.

---

## What works today (verified)

| Area | Status | Notes |
|------|--------|-------|
| Monorepo, contracts, docs | ✅ | pnpm + Turborepo. `@algaroshy/contracts` is used by the web app as the single source of types. |
| Database + migrations | ✅ | 22 SQLAlchemy models. Alembic initial revision. `alembic check` runs in CI. |
| Seed data | ✅ | 12 zones, 12 valves, 2 pumps, 2 sources, 15 sensors, admin user with a bcrypt-hashed password. |
| Auth | ✅ | `POST /auth/login` (JWT), `GET /auth/me`. Roles owner_admin / operator / viewer enforced on every endpoint. The simulator uses a service token. |
| Command service | ✅ | Whitelisted command types, target and payload validation, role permissions, interlocks (stale state, system mode, already running, duplicate, max concurrent zones, zone combinations, pump health, low tank, **open critical alarm**). Rejected commands are kept for the audit trail. Pending commands time out after 15 s, accepted ones after 180 s. A stop supersedes open starts. Every step goes to `event_log`. |
| Real-time | ✅ | `/ws?token=` sends `state.snapshot` on connect, then `zone.state.changed`, `pump.state.changed`, `system.mode.changed`, `command.updated`, `telemetry.stale`. The web app uses one shared connection and falls back to polling. |
| Simulator | ✅ | Plays the PLC and the farm. Timed start/stop sequences, flow validation, VFD booster curve, emitter √P flow, tank + well refill, direct-well fallback, soil moisture wetting/drying, seeded sensor noise. Protection for pump trip/failed start, valve stuck closed/open, no flow, leak, critical tank, e-stop and sensor fault. **Hydraulic constants are placeholders until the site survey.** |
| Alarm engine | ✅ | 20 codes from ALARM_MATRIX with AR/EN guidance, kept in sync with contracts by a test. Lifecycle ack → latched → reset → history. A "maintenance done" sign-off clears the repeated-fault alarm (ALM-036). Derived rules for tank low, pressure while irrigating, modes, stale data, comms lost, repeated faults and unauthorized attempts. Ack: operator+. Reset: admin. |
| Scenarios | ✅ | 13 scripted scenarios (SIMULATION_PLAN §5), run through the normal command path. Run from the Simulator page or `/sim/scenarios`. |
| Telemetry history | ✅ | Sampled every 10 s and kept for 7 days. `/telemetry/series` drives the zone charts. |
| Farm map | ✅ | Real zone shapes traced from the sketch (areas within ±12% of its legend, test-enforced). About 3,200 individual trees at real row spacing, with fruit following the season. Fly-to on zone select and on new S2/S3 alarms. Alarm rings, equipment glow, glass label chips. A tractor, birds, and a worker who walks to alarmed valves. Dirt tracks, buried mainline + laterals, valves, tank (closed concrete roof + level gauge), booster pad, control room + wellhead. Animations: water flowing in pipes (speed follows flow), drip rings and spreading damp soil under each tree on irrigating zones, canopy yellowing when dry, pump rotors, valve open/close, day/night lighting from farm local time. |
| Arabic-first UI | ✅ | Arabic by default with full RTL and an English toggle. Bundled IBM Plex Sans Arabic font (works offline). Logo + مزرعة الجروشي branding. Farm-local clock. Numbers stay Western digits. |
| Pages | ✅ | Dashboard, Zones (cards + filters), Equipment (pumps, valves, sensors), Alarm Center, Event log (`GET /events`), Simulator. The Simulator is admin-only behind a **presenter mode** toggle. |
| Start script | ✅ | `run.bat` / `run.sh` (dev) and `run.bat demo` (phones + PWA). One window, first-run self-setup, a single `API_PORT`, clean Ctrl+C shutdown, `stop.bat` safety net, `--smoke` self-test. `run.bat reset` clears operating history for a clean demo (keeps users and settings). |
| Phone / PWA | ✅ | Responsive layout with bottom navigation and a slide-in menu. Installable (manifest, icons, service worker that never caches `/api` or `/ws`). |
| Web MVP | ✅ | Real login, live map (incl. starting/stopping state), dashboard side column (tank, pumps, alarms, trends, water today), zone panel with a duration picker + confirm and real history, start/stop with interlock feedback, alarm chime + mute, reduce-motion toggle, global STOP ALL, Alarm Center (active/history, ack/reset, AR/EN guidance), Simulator page, honest connection status. |
| Tests + CI | ✅ | 72 API + 22 simulator + 22 web + 3 map-model tests. GitHub Actions: ruff, pytest, migrations, eslint, typecheck, build, vitest.  |

## Live scenario suite (2026-11-18)

All **13/13** scenarios pass against the running API + simulator (timescale 1×): normal cycle, direct-well cycle, tank critical during a run, booster failed start, pump trip mid-cycle, valve failed open, no flow, valve failed close, mainline leak, emergency stop, comms loss, repeated fault, reset farm. The first live runs found 4 real bugs, now fixed with regression tests (see CHANGELOG).

## Known gaps (not done — don't demo these as real)

| Gap | Planned in |
|-----|-----------|
| Schedules, irrigation cycle log, reports | D |
| All AI features (`/health` reports `ai: not_implemented`) | E |
| PLC adapter, hosting, PostgreSQL in production, notifications/SMS | Production track |
| Notifications (push/email/SMS) and escalation for alarms | Production track |
| Scenario suite runs manually against a live stack, not in CI | D |
| Pipe routes are a plausible guess. Edit `tools/map-geometry/network.py` with the real routes | Owner input |
| Weather location: need the farm's longitude (the sketch only shows ≈32.51°N) | Owner input → E |
| Dual-zone operation (`MAX_CONCURRENT_ZONES>1`) is supported by interlocks but not exercised by any scenario | After commissioning |

## Milestones

| Milestone | Status |
|-----------|--------|
| **A: Foundations** | ✅ Done 2026-11-18 |
| **B: Credible simulator + real alarms** | ✅ Done 2026-11-18 |
| **C: Demo-quality UI + PWA** | ✅ Done 2026-11-18 |
| **D: Schedules, cycles, reports** | ⬜ Next |
| **E: AI (alarm assistant, weather advisor, anomaly detection)** | ⬜ |
| Production track (PLC adapter, hosting, hardening) | ⬜ After the demo |

## Decisions

| Item | Status |
|------|--------|
| Zones | ✅ 12, from the farm layout SVG |
| Mobile | ✅ PWA from the web app (no separate React Native app) |
| Order | ✅ Foundations → demo polish → production |
| PLC model / protocol | ❓ Not decided. The adapter stays protocol-neutral. |
| Hosting | ❓ Not decided. Comes after the demo. |
| Pump specs, valve sizes, pipe diameters | ❓ Need a site survey (affects simulator constants and thresholds) |
