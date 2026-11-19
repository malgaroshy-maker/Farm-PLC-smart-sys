# Prompt — Milestone D, step 0 follow-up: sim-time review fixes

Paste this into the agent session that built the `sim-time` branch, or into a fresh session at the repo root.

---

The virtual farm clock on branch `sim-time` was reviewed (commits 9699aef..4d66c2d). All suites pass and speed, badge, pause and the reset dialog work live. **But the review found a blocker and several issues.** Fix all of them on `sim-time`, following the owner's decisions below. Read `docs/SIMULATION_TIME.md` first. Its "Owner decisions" table still applies.

## 1. BLOCKER: pumps can never start after a jump or "Back to real time"
- `apps/simulator/src/engine.py` → `jump()` sets `pump.state = "off"`. Pumps only restart from `"stopped"`/`"cooldown"` (`_step_pumps`), so after any jump, or after "Back to real time" (which the simulator also handles as a jump), every start sits in `starting_pump` until it times out. Only a simulator restart recovers. Reproduced live at 10× and at 1×.
- Fix: put pumps into a valid stopped state (`"stopped"`, `run_fb=False`, and clear `pump_t`). While you're there, reset the per-zone/valve phase timers (`phase_t`, `zone_abort`, `zone_cmd`) for the zones you stop, so nothing stale survives the jump.
- **Regression tests (simulator):** after `jump()` forward, *and* after a backward jump/reset, start a zone and assert it reaches `running`, with the pump `running`. Add the same check to the API/live flow if you can.

## 2. Command times mix clocks
- The simulator sends `completed_at` / `acknowledged_at` in real time (`engine.py` `_update()`), and the API stores them as-is (`services/commands.py` `sync_command`), while `requested_at` is farm time. Live, a start was "requested 20 Nov" and "completed 19 Nov". That would break run durations in the upcoming cycle log.
- Fix: **the API is the single source of farm time.** In `sync_command`, ignore controller-supplied timestamps for these fields and stamp `clock.farm_now()` on receipt. Keep any controller timestamp only as optional metadata if you need it. Remove the timestamps from the simulator payload, or leave them unused.
- Test: at speed 360, the `completed_at` and `acknowledged_at` of a synced command are ≥ `requested_at` and in farm time.

## 3. Service token printed in the simulator log
- `apps/simulator/src/client.py:98` prints the WebSocket URL, including `?token=…`. Print the host only, never the token. Check that no other log line prints a token or password.

## 4. Smaller correctness fixes
- **Scenario alarm check mixes clocks** (`services/scenarios.py`, `wait_alarm`): `Alarm.triggered_at` (farm time) is compared with `self._started` (real time). After a pause, farm time is behind real time, so a raised-then-cleared alarm can be missed. Record the run start in farm time as well, and compare farm with farm. Real time stays for the step timeouts.
- **Water-today gap limit** (`services/telemetry.py`, `MAX_GAP_S` raised from 60 s to 600 s): at 1× this now counts flow across a 10-minute outage. Make the limit follow the sampling spacing (about 3 × the expected farm-time spacing, i.e. 3 × max(10 s, speed × 1 s) for the speed in effect), so it's about 60 s at 1× and wide enough at 360×. If the speed per sample isn't known, derive it from the `clock.*` events, or store it on the sample. Pick the simplest correct option and explain it. Add tests at 1× (gap not integrated) and 360× (normal spacing integrated).
- Remove the duplicate `return len(latched)` in `services/alarms.py` `reset_all_cleared`.
- Remove the hidden `normal_day` → `normal_cycle` alias in `scenarios.py`. Use `normal_cycle` in docs and prompts instead.

## 5. Repo hygiene (owner decisions)
- **Delete** the `screenshots/` folder and `scripts/test_live_check.py` from the branch, and add `screenshots/` to `.gitignore`. Verification belongs in your report, not the repo.
- **Revert the reformat** of `apps/api/alembic/versions/0356f537da66_initial_schema.py` to its `master` version (`git checkout master -- <file>`). Exclude `alembic/versions/` from `ruff format` (pyproject `extend-exclude`) so it doesn't happen again. Keep your new migration `2c8a7d3b5e1f` as it is.

## 6. Verify
- All suites green: `pytest` in `apps/api` and `apps/simulator`, `ruff check` + `ruff format --check` (excluding migrations), and `npx vitest run`, `npx eslint .`, `pnpm build` in `apps/web`. Also `alembic upgrade head` on a fresh DB.
- **Live:** run **exactly one** simulator (check that no old `src.main` process is still running). Then:
  1. At 10×, start a zone, let it reach `running`, jump to 05:30, and confirm the zone stopped.
  2. **Start a zone again and confirm it reaches `running`.**
  3. Click "Back to real time" and confirm, then start a zone again and confirm it reaches `running`.
  4. Check in the Event log that the command times are in order.
- Update `CHANGELOG.md` (Unreleased, under the sim-time entry) and the test counts in `PROJECT_STATUS.md`.

## Rules
- Commit on `sim-time` only. **Don't merge to master and don't push.** The owner's reviewer will review again, and the owner approves the merge.
- The UI is Arabic first with an English toggle, and any new strings go in `lib/i18n.ts` in both languages.
- Never print secrets or passwords, in code or in your report.
- Report honestly: what you fixed, how you verified it (with command output), and anything you couldn't verify.
