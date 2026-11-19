# Prompt — Milestone D, step 0: simulation time

Paste this into a fresh agent session at the repo root.

---

You are continuing the Algaroshy Farm smart-irrigation project (pnpm + Turborepo monorepo: FastAPI API in `apps/api`, Python PLC/farm simulator in `apps/simulator`, React 19 + Vite + Tailwind v4 web app in `apps/web`, shared types in `packages/contracts`). Milestones A–C and UI round 2 are done and on `master`.

**Your task: build the virtual farm clock exactly as specified in `docs/SIMULATION_TIME.md`.** The owner has already decided every point in its "Owner decisions" table, so don't change them. If something isn't covered by the spec and affects what users see, ask the owner before deciding.

Read first: `docs/SIMULATION_TIME.md`, `PROJECT_STATUS.md`, `docs/AUDIT_AND_ROADMAP.md` (Milestone D), `apps/api/app/core/timeutil.py`, `apps/api/app/services/{alarms,telemetry,commands,live_state,scenarios}.py`, `apps/api/app/routers/sim.py`, `apps/simulator/src/{engine,main}.py`, `apps/web/src/layouts/DashboardLayout.tsx` (header clock), `apps/web/src/components/map/FarmMap.tsx` (`farmNow`, lighting, `month`), `apps/web/src/lib/presenter.ts`, `apps/web/src/pages/SimulatorPanel.tsx`, `apps/api/app/reset_demo.py`.

Deliver, in this order:
1. **API clock:** `app/core/clock.py` (`FarmClock`, persisted one-row table + Alembic migration, monotonic, locked to real time unless `CONTROLLER_MODE=simulator`). Add `GET`/`POST /api/v1/sim/clock` (POST is admin only), `clock.*` events in the event log, and the `clock.changed` WS event. Include `farm_now` and `speed` in `state.snapshot`.
2. **Switch farm-facing timestamps to `farm_now()`** per the spec's table. Link-health checks (staleness ALM-044/029, command timeouts, JWT, debounce) stay on real time. Add a guard test so the wrong clock can't creep back in.
3. **Telemetry sampling:** every 10 s of farm time, at most once per real second, stored with farm timestamps. Retention is in farm time.
4. **Simulator:** follow the API clock (read on start, then the WS `clock.changed`). Physics dt = real dt × speed with sub-stepping. Pause means no physics but keep publishing state. Jump = stop running zones, apply a closed-form drying/refill for the skipped time, log it. `TIMESCALE` becomes the initial speed only.
5. **"Back to real time":** confirm → reuse `reset_history()` from `app/reset_demo.py` → clock resyncs to real time at 1×.
6. **Web:** `useFarmClock()` hook used by every clock (header, map lighting, seasonal sprites, chart labels, event times, water-today). Amber **SIMULATED TIME** badge with the speed (Arabic + English, i18n keys). A presenter-mode header chip (pause/play, speed 1×/10×/60×/360×, jump-to-time, step +1 min). A full panel on the Simulator page including "Back to real time" with a confirm dialog that explains history will be cleared. Admin only. On phones, show just the badge.
7. **Tests** listed in the spec, plus: all existing tests stay green (`pytest` in `apps/api` and `apps/simulator`; `npx vitest run`, `npx eslint .` and `pnpm build` in `apps/web`; `ruff check`).
8. **Live check:** start with `run.bat reset` (or the preview servers). Run `normal_cycle` at 360×, then confirm in the browser that the header clock, the badge, day/night, charts and water-today agree. Then try pause, jump to 05:30 and back to real time.
9. **Docs:** CHANGELOG (Unreleased), PROJECT_STATUS (move the "Simulation time" known gap to "What works", and update test counts), and mark step 0 done in `docs/AUDIT_AND_ROADMAP.md` and `docs/SIMULATION_TIME.md`.

Rules for this repo:
- The UI is Arabic first, with RTL and an English toggle. Every new string goes in `apps/web/src/lib/i18n.ts` with both languages.
- Dark HMI style: glass panels (`.panel`), cyan accent `#00e5ff`, amber `#ff9f43` for simulated time. Use the duotone icons in `components/icons/FarmIcons.tsx` where one fits.
- Respect reduce motion (`lib/prefs.ts`).
- Commands still go only through the command service and its interlocks.
- Don't print secrets or passwords. Commit on a branch (`sim-time`). Don't push or merge to `master` until the owner says so.
- Report honestly: say what you verified in the browser and what you didn't.
