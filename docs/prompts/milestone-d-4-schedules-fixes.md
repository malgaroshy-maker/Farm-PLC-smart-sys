# Prompt — Milestone D follow-up: review fixes for schedules, cycles and reports

Paste this into the agent session that built `milestone-d-schedules`, or into a fresh session at the repo root.

---

Branch `milestone-d-schedules` (74a1110..ff99ec0) was reviewed.
- **What works:** all suites pass (API 112, simulator 27, web 32), and the new migration applies to a fresh DB. Live, a 3-zone program ran in order at 60× and logged 3 completed cycles with water. The conflict checker rejects overlaps, including across midnight, and max-runtime violations. The CSV has Arabic headers and a UTF-8 BOM.
- **What doesn't:** the review found the bugs below.

Fix all of them on `milestone-d-schedules`. The owner confirmed the decisions in `docs/SCHEDULES.md`, so keep them. Read `docs/SCHEDULES.md`, `docs/SIMULATION_TIME.md` and `docs/ALARM_MATRIX.md` first.

## 1. MUST FIX — Reports date range does nothing
- `apps/web/src/pages/Reports.tsx` sends `?from_date=&to_date=`, but `apps/api/app/routers/reports.py` declares `Query(alias="from")` / `alias="to"`. The range is ignored, so Today, 7 days and 30 days all return the default range.
- The default range is also off by one: "last 7 days" returns **8** dates (2026-11-12 → 2026-11-19) while the heading says 11-13 → 11-19.
- Fix both:
  - one parameter name on both sides (match `docs/API.md`)
  - inclusive farm-local dates
  - "Today" = 1 day, "Last 7 days" = 7 days
- Tests: API (each range returns exactly N dates, Africa/Tripoli dates) and web (the request uses the right params).

## 2. MUST FIX — "Total cycles" and aborted column show NaN
- The web expects fields the API doesn't send. Daily rows have `cycles_count`, `completed_count`, `total_water_m3`, `total_duration_min`, but the page reads `aborted_count`, `skipped_count` and a total that doesn't exist.
- Fix: return `aborted_count`, `skipped_count`, `faulted_count` and `manual_stop_count` per day from the API, add them to `packages/contracts`, and use the shared type in the page so a mismatch fails the typecheck.
- Make the summary cards add up: total = completed + aborted + skipped + faulted + manual stop.
- Never show `NaN`. Missing values render as `0` or `—`.
- Check the other three tabs (water per zone, pump runtime, alarm history) for the same kind of mismatch.

## 3. Skipped step raises the wrong alarm (owner decision: new S1 info alarm)
- `services/scheduler.py` raises **ALM-035 "Unauthorized command attempt"** (a security alarm) when an interlock blocks a scheduled step.
- Add a dedicated code **ALM-045 "Scheduled step skipped" / "تم تخطي خطوة مجدولة"**:
  - category `schedule`, severity **S1**
  - momentary (raised as a one-shot event like `raise_event`), no ack required, no manual reset
  - AR/EN message plus guidance ("Check the reason in the cycle log: low tank / critical alarm / zone busy / system not in auto", in Arabic too)
  - the skip reason in `detail`
- Keep the three copies in sync:
  - `apps/api/app/core/alarm_catalog.py`
  - `packages/contracts/src/alarms.ts`
  - `docs/ALARM_MATRIX.md`

  The contracts-sync test must cover it.
- Test: a blocked scheduled step raises ALM-045, never ALM-035, and the program continues with the next step.

## 4. Scenarios leave enabled programs behind (owner decision: delete)
- `services/scenarios.py` creates `prog_scen_*` programs, e.g. "Low Tank Sequence", enabled daily at 07:00, and never removes them. They then fire every day in the demo.
- Fix: delete scenario-created programs (and their steps and `scheduler_state` keys) when the scenario finishes, fails or is stopped. Use `try/finally`.
- Add a one-time cleanup that removes any leftover `prog_scen_*` programs: at API start-up, or in the migration as a data step if that's cleaner. Explain your choice.
- Make `reset_demo` remove them too.
- Test: after each scenario (pass and fail paths), no `prog_scen_*` program exists.

## 5. Jump detection must scale with speed
- `MISSED_RUN_GAP_SEC = 900` farm seconds. At 360×, one monitor tick that runs about 3 s late looks like a jump, and a real start gets marked "missed".
- Fix: decide "jump/downtime" from **real** elapsed time between ticks (e.g. more than 30 real seconds), or from an explicit jump signal (`scheduler.on_clock_jump`, `clock.jumped` event). Don't use a fixed farm-seconds gap.
- Within a normal tick, fire every start time that falls in `(prev, now]`, even if the window is several farm-minutes wide at 360×.
- Tests at 360× with a late tick (5 real s): the start fires once and isn't missed. A real jump still applies the "missed" rule.

## 6. Close stuck open cycles
- A cycle opens when a start is accepted (`submit_command`) but only closes on a zone state change (`routers/state.py`). If the start fails or times out **before the zone moves** (controller never picks it up, valve fails before the state changes, superseded), the row stays open forever.
- Fix: when a start command reaches a terminal failure (`failed`, `timed_out`, `rejected`, superseded) and its zone never became active, close its cycle as `aborted`, copying `failure_reason`.
- Do this in one place (command terminal handling) so it can't drift from the zone-state path, and close each cycle exactly once.
- Also make sure "Back to real time" and `reset_demo` leave no open cycles.
- Tests: timeout before pickup, superseded start, valve failure → exactly one closed `aborted` cycle each. No open cycles remain.

## 7. Honest water estimate
- `services/cycles.py` `integrate_zone_water_m3`: when integration gives 0 but there are flow samples, it uses `avg_flow × whole duration`. With one sample this invents water.
- Fix:
  - Integrate the samples that exist.
  - If there are fewer than 2 usable samples, store the best estimate and mark it as estimated: add `water_is_estimate: bool` to the cycle (migration + contracts).
  - Show "≈" in the zone panel, the cycle list and reports when it's estimated.
- "Water today" and reports must use the same number.
- Tests: 0 samples, 1 sample (estimated), normal run (not estimated).

## 8. Smaller items
- Untranslated labels in `Reports.tsx`: "Completed Cycles", "Water (m³)", "Detailed Records" (and any other hard-coded English). Move all of them to `lib/i18n.ts` in Arabic and English. Add an i18n check that fails on hard-coded English strings in the new pages if practical.
- **Split the web bundle:** lazy-load the Reports, Schedules and Simulator pages (and recharts with them), with a small loading state. Get the main chunk under 500 kB and report the chunk sizes before and after.

## 9. Verify
- All green:
  - `pytest` + `ruff check` + `ruff format --check` (api, simulator)
  - `npx vitest run`, `npx eslint .`, `pnpm build` (web): no chunk-size warning
  - `alembic upgrade head` on a fresh DB, and on the existing `farm.db`
- **Live:**
  - Run **exactly one** API and **one** simulator, and stop any leftover `src.main` / `uvicorn` processes you started earlier. Start from `run.bat reset`.
  1. Create a 3-zone program in the **UI** (not the API). Jump to 5 minutes before it, set 360×, and confirm all 3 steps fire without any being marked "missed".
  2. Cause a blocked start (e.g. low tank) and confirm ALM-045, a skipped cycle, and that the program continues.
  3. Run a scenario and confirm no `prog_scen_*` program is left.
  4. On Reports, switch Today / 7 days / 30 days and confirm the dates and row counts change and no NaN appears. Download a CSV from each tab.
  5. Open the zone panel and confirm the cycle list, with "≈" on estimated water.
  6. Return to real time.
- Docs: `docs/SCHEDULES.md` (implementation notes for items 3–7), `docs/ALARM_MATRIX.md`, `docs/API.md`, `CHANGELOG.md`, and the test counts in `PROJECT_STATUS.md`.

## Rules
- Commit on `milestone-d-schedules` only. **Don't merge or push.** The owner's reviewer reviews again, then the owner approves the merge.
- New migrations only. Never edit old ones.
- Farm-facing times use `clock.farm_now()`, and link-health checks use real time (see the guard test).
- Arabic-first i18n for every new string. Glass `.panel` style and FarmIcons.
- Never print secrets. Don't commit screenshots or throwaway scripts.
- Report honestly: what you fixed, how you verified it (with command output), and anything you couldn't verify.
