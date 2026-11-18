# 📊 Project Status — Algaroshy Farm Smart Irrigation System

**Last Updated:** 2026-11-18
**Current milestone:** A ✅ done → next is **B: credible simulator + real alarms**
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
| Command service | ✅ | Whitelisted command types, target and payload validation, role permissions, interlocks (stale state, system mode, already running, duplicate, max concurrent zones, zone combinations, pump health, low tank). Rejected commands are kept for the audit trail. Commands time out after 15 s. Every step goes to `event_log`. |
| Real-time | ✅ | `/ws?token=` sends `state.snapshot` on connect, then `zone.state.changed`, `pump.state.changed`, `system.mode.changed`, `command.updated`, `telemetry.stale`. The web app uses one shared connection and falls back to polling. |
| Simulator (basic) | ✅ | Start/stop/stop_all/set_mode. Authenticated. Retries until the API is up. **The physics is still a placeholder** (Milestone B). |
| Web MVP | ✅ | Real login, live map + zone drawer, start/stop with interlock feedback, global STOP ALL, honest connection status (LIVE / POLLING / STALE / OFFLINE), role-aware controls. |
| Tests + CI | ✅ | 41 API tests + 5 simulator tests. GitHub Actions: ruff, pytest, migrations, eslint, typecheck, build. |

## Known gaps (not done — don't demo these as real)

| Gap | Planned in |
|-----|-----------|
| Alarm engine, alarm API, ack/reset (Alarm Center shows live data, but nothing raises alarms yet) | B |
| Realistic simulator physics, timed valve travel, flow validation, faults with consequences, scenarios | B |
| Telemetry history (the zone chart is labelled SAMPLE DATA) | B |
| Valves and sensors are not loaded into the simulator, so valve fault injection fails | B |
| Arabic/RTL UI, real zone polygons, PWA/mobile layout, more pages | C |
| Schedules, irrigation cycle log, reports | D |
| All AI features (`/health` reports `ai: not_implemented`) | E |
| PLC adapter, hosting, PostgreSQL in production, notifications/SMS | Production track |
| Web unit tests (Vitest). CI covers lint, typecheck and build only for now. | B |

## Milestones

| Milestone | Status |
|-----------|--------|
| **A: Foundations** | ✅ Done 2026-11-18 |
| **B: Credible simulator + real alarms** | ⬜ Next |
| **C: Demo-quality UI + PWA** | ⬜ |
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
