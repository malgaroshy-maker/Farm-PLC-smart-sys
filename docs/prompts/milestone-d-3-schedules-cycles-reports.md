# Prompt — Milestone D, steps 1–4: schedules, cycle log, reports

Paste this into a fresh agent session at the repo root.

---

You are continuing the Algaroshy Farm smart-irrigation project:
- pnpm + Turborepo monorepo
- FastAPI API in `apps/api`
- Python PLC/farm simulator in `apps/simulator`
- React 19 + Vite + Tailwind v4 web app in `apps/web`
- shared types in `packages/contracts`

Milestones A–C, UI round 2 and **Milestone D step 0 (the virtual farm clock)** are done and on `master`.

**Your task: Milestone D steps 1–4 — schedules, the scheduler, the irrigation cycle log, and reports** (`docs/AUDIT_AND_ROADMAP.md` → Milestone D).

## 0. Read first
- `PROJECT_STATUS.md`, `docs/AUDIT_AND_ROADMAP.md` (Milestone D), `docs/SIMULATION_TIME.md` (clock rules: farm time vs real time), `docs/API.md` §5 Schedules and §9 Reports, `docs/PLC_CONTROL_LOGIC.md` (sequences, interlocks, max concurrent zones), `docs/DATABASE_SCHEMA.md`.
- Code:
  - `apps/api/app/models/{schedule,irrigation_cycle,zone,command}.py` (the `schedules` and `irrigation_cycles` tables already exist and are unused)
  - `apps/api/app/services/{commands,monitor,telemetry,alarms,events}.py`
  - `apps/api/app/core/clock.py`, `apps/api/app/core/domain.py`, `apps/api/app/routers/zones.py`
  - `apps/simulator/src/engine.py` (how a run starts, runs and stops)
  - `apps/web/src/{layouts/DashboardLayout.tsx,pages/*,components/ZoneDrawer.tsx,lib/i18n.ts,lib/clock.ts,index.css}`

## 1. Ask the owner BEFORE building (mandatory)
The owner wants to be asked about every behaviour and UI choice. Ask these in **one round**, each as a multiple-choice question with your recommendation first, then build exactly what they choose. Don't decide any of these yourself.

1. **Schedule shape:** only one zone may run at a time (`max_concurrent_zones = 1`). Options:
   - (a) **Programs** *(recommended)*: a named program with a start time and days, running an ordered list of zones and durations one after another.
   - (b) **Per-zone schedules**: each zone gets its own time.
2. **Overlaps:** when two runs would overlap:
   - reject at save time with a clear conflict message *(recommended)*, or
   - queue the later one automatically.
3. **Blocked start:** a scheduled start can be refused by an interlock (open critical alarm, low tank, a zone already running, system not in auto). Options:
   - skip that zone, log it, raise an S1 info alarm, and continue the program *(recommended)*
   - retry for N minutes
   - abort the whole program
4. **Missed runs** (API was down, or the farm clock jumped past a start time):
   - skip and log "missed" *(recommended)*, or
   - catch up immediately.
5. **Schedules page layout:**
   - a **day timeline** (24 h bar per day of the week, programs as blocks) plus an edit drawer *(recommended)*
   - a plain list/table
   - a weekly calendar grid
6. **Who can edit schedules:** admin only, or operator+ *(recommended: operator+ can enable/disable, admin creates and edits)*.
7. **Cycle log scope:**
   - log manual and scenario runs as well as scheduled ones *(recommended)*, or
   - log scheduled runs only.
8. **Reports page:**
   - one page with tabs (daily irrigation · water per zone · pump runtime · alarm history), date range picker, charts + table, CSV export *(recommended)*, or
   - separate pages.
   - Also ask whether the CSV export should use Arabic headers when the UI is in Arabic (recommended: yes, UTF-8 with BOM so Excel opens it correctly).
9. **Dashboard:** add a "Next irrigation" card to the side column and phone status card (program, zone, time and countdown)? *(Recommended: yes.)*

Record the answers in a new **`docs/SCHEDULES.md`** ("Owner decisions" table + design) before writing code.

## 2. Build (after the answers)

### 2a. Schedules API
- Use the existing `schedules` table, or add a `programs` + `program_steps` model if the owner picks programs, with an Alembic migration (never edit old migrations).
- CRUD under `/api/v1/schedules`, following `docs/API.md` §5. Permissions as decided. Add an enable/disable toggle.
- **Conflict checker** (pure function, unit-tested):
  - overlapping runs in farm local time, across days and weekdays
  - forbidden zone combinations (`zone_combinations`)
  - `max_runtime_min` per zone
  - pump capacity / `max_concurrent_zones`
  - Return structured conflicts with AR/EN messages.
- `GET /api/v1/schedules/upcoming?hours=24` → next runs in farm time (feeds the dashboard card).

### 2b. Scheduler service (on the farm clock)
- **Do not use APScheduler's wall-clock triggers.** They run on real time and would break simulation time. Drive the scheduler from the existing monitor loop using `clock.farm_now()`:
  - Each tick, find runs that are due since the last tick.
  - Store the last fired occurrence per schedule/program step so nothing fires twice (persist it; it must survive restarts).
  - Handle pause (nothing fires), speed changes and jumps (apply the owner's "missed runs" rule; a jump must never mass-fire runs).
  - Remove the unused `apscheduler` dependency if nothing else needs it.
- Issue commands **only through `submit_command`** with `actor_type="scheduler"`, so every interlock applies. Never write zone state directly.
- For programs: start the next step only after the previous zone has really finished (`command` terminal and zone back to idle), not just after its time has passed. Apply the owner's "blocked start" rule.
- Events: `schedule.fired`, `schedule.skipped` (with reason), `schedule.missed`, `program.started`, `program.finished`. Broadcast what the UI needs over WS (add new events to `docs/REALTIME_EVENTS.md`).

### 2c. Irrigation cycle log
- One `irrigation_cycles` row per run (manual / scheduled / scenario, per the owner's choice), created when a start is accepted and closed when the zone returns to idle. Fields:
  - planned start / duration and actual start / end / duration (**farm time**)
  - outcome (`completed | aborted | faulted | manual_stop | skipped`)
  - initiator
  - water used (m³) integrated from `zone.flow_m3h` telemetry over the run, reusing the integration in `services/telemetry.py` with its speed-aware gap limit
  - linked alarm codes raised during the run
- Hook it into command sync / zone state changes in one place, so it can't drift. It must be correct at 360× and across pause and jump (a jump stops the running zone → outcome `aborted`, with reason "clock jump").
- `GET /api/v1/cycles?zone_id&from&to&outcome` with pagination.
- Show the last few cycles in the zone panel's history section.
- Switch **"water today"** to the cycle log, falling back to telemetry for a run still in progress, so the dashboard and reports agree.

### 2d. Reports
- `docs/API.md` §9: `/reports/daily-irrigation`, `/reports/water-usage`, `/reports/pump-runtime`, `/reports/alarm-history`.
  - Ranges are in farm local dates (Africa/Tripoli).
  - Add a `?format=csv` variant per the owner's CSV decision.
- Web Reports page per the owner's layout choice: recharts charts plus a table, date range picker, and empty states (reuse `components/EmptyState.tsx`).
- Add a nav entry with a FarmIcons icon (add a new duotone icon in `components/icons/FarmIcons.tsx` if none fits; match the existing style).

### 2e. Web — Schedules
- A Schedules page in the chosen layout, with create/edit in a drawer:
  - zone/step picker with crop icons
  - time and days
  - duration chips (15/30/45/60, as in the zone panel) plus a slider up to `max_runtime_min`
  - live conflict feedback from the API while editing
  - a confirm step on save
- If the owner said yes, the "Next irrigation" card on the dashboard side column and in the phone status card, ticking on `useFarmClock()` so it follows simulation time.
- Every new string goes in `lib/i18n.ts` (Arabic first, plus English). Use the glass `.panel` style, cyan `#00e5ff` and FarmIcons. Respect reduce motion. Check the layout at phone width.

### 2f. Simulator scenario
- Add a `scheduled_day` scenario: create a short program (e.g. 3 zones × 2 min), jump to just before its start, run at 60×, and assert three completed cycles with water > 0. Add a blocked-start variant (e.g. low tank) that checks the owner's "blocked start" rule.

## 3. Tests (minimum)
- Conflict checker: overlap across midnight, weekday masks, combinations, max runtime.
- Scheduler:
  - fires once per occurrence
  - nothing fires while paused
  - at 360×, each occurrence still fires exactly once
  - a jump past a start follows the "missed" rule and doesn't mass-fire
  - survives an API restart without double-firing
  - goes through interlocks (a critical alarm blocks it)
- Cycle log: completed / aborted / manual stop / jump; water matches the telemetry integration; times are farm time and ordered.
- Reports: totals match the cycle log; CSV has the right headers, encoding and farm-local dates.
- Web: the conflict UI, the next-irrigation countdown with the clock store, and an i18n key check.
- Keep everything green: `pytest` + `ruff check` + `ruff format --check` (api, simulator), and `npx vitest run`, `npx eslint .`, `pnpm build` (web). Run `alembic upgrade head` on a fresh DB.

## 4. Live check (browser)
Run **exactly one** simulator (check no old `src.main` process is running), and start from `run.bat reset` or a clean DB. Then:
1. Create a program in the UI.
2. Jump to 5 minutes before it and set 60×.
3. Watch the zones run in order on the map.
4. Check the cycle log, water today, the next-irrigation card, and each report tab with a CSV download.
5. Trigger a blocked start and check it's handled the way the owner chose.
6. Return to real time.

Report what you saw. If you take screenshots, keep them outside the repo.

## 5. Docs
- `docs/SCHEDULES.md` (decisions + design)
- `docs/API.md` (final endpoints)
- `docs/REALTIME_EVENTS.md`
- `CHANGELOG.md` (Unreleased)
- `PROJECT_STATUS.md`: move schedules, cycle log and reports to "What works", update test counts, and mark Milestone D done only if everything above works.
- `docs/AUDIT_AND_ROADMAP.md`: mark steps 1–4.

## Rules
- Work on branch `milestone-d-schedules`. Commit in logical steps. **Don't merge to master and don't push.** The owner's reviewer reviews first, and the owner approves the merge.
- Commands go only through the command service and its interlocks. The scheduler is just another actor.
- Farm-facing times use `clock.farm_now()`. Link-health checks stay on real time (see the guard test in `apps/api/tests/test_clock_guard.py`, and extend its whitelist only with a comment explaining why).
- Don't edit existing migrations. Never print secrets or passwords. Don't commit screenshots or throwaway scripts.
- Report honestly: what you built, how you verified it (with command output), and anything you couldn't verify.
