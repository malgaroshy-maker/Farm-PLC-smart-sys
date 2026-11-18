# 📊 Project Status — Algaroshy Farm Smart Irrigation System

**Last Updated:** 2026-11-18
**Current milestone:** A ✅ · B ✅ → next is **C: demo-quality UI + PWA**
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
| Alarm engine | ✅ | 20 codes from ALARM_MATRIX with AR/EN guidance, kept in sync with contracts by a test. Lifecycle ack → latched → reset → history. Derived rules for tank low, pressure while irrigating, modes, stale data, comms lost, repeated faults and unauthorized attempts. Ack: operator+. Reset: admin. |
| Scenarios | ✅ | 13 scripted scenarios (SIMULATION_PLAN §5), run through the normal command path. Run from the Simulator page or `/sim/scenarios`. |
| Telemetry history | ✅ | Sampled every 10 s and kept for 7 days. `/telemetry/series` drives the zone charts. |
| Web MVP | ✅ | Real login, live map (incl. starting/stopping state), zone drawer with real history, start/stop with interlock feedback, global STOP ALL, Alarm Center (active/history, ack/reset, AR/EN guidance), Simulator page, honest connection status. |
| Tests + CI | ✅ | 66 API + 22 simulator + 10 web (Vitest) tests. GitHub Actions: ruff, pytest, migrations, eslint, typecheck, build, vitest.  |

## Live scenario suite (2026-11-18)

All **13/13** scenarios pass against the running API + simulator (timescale 1×): normal cycle, direct-well cycle, tank critical during a run, booster failed start, pump trip mid-cycle, valve failed open, no flow, valve failed close, mainline leak, emergency stop, comms loss, repeated fault, reset farm. The first live runs found 4 real bugs, now fixed with regression tests (see CHANGELOG).

## Known gaps (not done — don't demo these as real)

| Gap | Planned in |
|-----|-----------|
| Arabic/RTL UI, real zone polygons, PWA/mobile layout, more pages | C |
| Schedules, irrigation cycle log, reports | D |
| All AI features (`/health` reports `ai: not_implemented`) | E |
| PLC adapter, hosting, PostgreSQL in production, notifications/SMS | Production track |
| Notifications (push/email/SMS) and escalation for alarms | Production track |
| Scenario suite runs manually against a live stack, not in CI | C |
| Dual-zone operation (`MAX_CONCURRENT_ZONES>1`) is supported by interlocks but not exercised by any scenario | After commissioning |

## Milestones

| Milestone | Status |
|-----------|--------|
| **A: Foundations** | ✅ Done 2026-11-18 |
| **B: Credible simulator + real alarms** | ✅ Done 2026-11-18 |
| **C: Demo-quality UI + PWA** | ⬜ Next |
| **D: Schedules, cycles, reports** | ⬜ |
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
