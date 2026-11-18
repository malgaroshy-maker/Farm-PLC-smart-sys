# Simulation time — one virtual farm clock

**Status:** ✅ done (2026-11-19). This is the first item of Milestone D, because schedules depend on the clock. All owner decisions and implementation requirements delivered and verified with automated test suites and live Playwright execution.

## Why
Today `TIMESCALE` in `.env` only speeds up the simulator's physics (tank, moisture, runtimes), and it's fixed when the simulator starts. Everything else still runs on the real wall clock: the API timestamps, the header clock, day/night lighting, seasonal fruit, "water today", telemetry charts, and the 24 h window of ALM-036. At 60× these drift apart, so the demo looks wrong.

**Goal:** in simulator mode, a full irrigation day can be shown in a few minutes, and every part of the app agrees on what time it is on the farm.

## Owner decisions
| Topic | Decision |
|-------|----------|
| Purpose | **One shared virtual farm clock.** Schedules, day/night, seasonal sprites, charts, water-today, alarm windows and event times all follow it. |
| Control | **Live control in presenter mode** (admin only). Controls sit on the Simulator page, plus a small header chip while presenter mode is on. Changes apply instantly, with no restart. |
| Speeds | Pause, 1×, 10×, 60×, 360×. |
| Tools | **Jump to a time of day** (e.g. 05:30). **Pause / step** (freeze, or advance one simulated minute). A clear **"SIMULATED TIME" badge** on every clock while the farm clock is not real time. A **"Back to real time"** button. |
| Back to real time | Asks for confirmation, then **clears the demo history** (alarms, commands, events, telemetry, snapshots, the same as `run.bat reset`). Users and settings are kept. Then it resyncs to the real Africa/Tripoli clock at 1×. |
| Real PLC | **Locked to real time.** Simulation time exists only in simulator mode. With a real PLC adapter, the clock is always real and the controls are hidden. |

## Design

### The clock (API, single source of truth)
`app/core/clock.py` → `FarmClock`:
- State: `mode` (`real` | `sim`), `speed` (0 = paused), `anchor_real` (UTC), `anchor_sim` (UTC).
- `farm_now() = anchor_sim + (real_now − anchor_real) × speed`. In `real` mode, `farm_now() = real_now`.
- Every change (speed, pause, jump) re-anchors first, so the clock never jumps by accident.
- **Monotonic:** the farm clock only moves forward. A jump goes to the *next* occurrence of the chosen time. The only way back is "Back to real time", which clears history first.
- Persisted (a one-row table, with an Alembic migration), so an API restart keeps the simulated day.
- Locked to `real` unless `CONTROLLER_MODE=simulator` (a new setting, default `simulator` for now).

### Which timestamps follow which clock
| Farm clock (`farm_now`) | Real clock (`utcnow`) |
|---|---|
| telemetry `ts`, alarm `triggered_at` / `cleared_at` / `acknowledged_at` / `reset_at`, event `occurred_at`, command `requested_at` / `completed_at` (as shown to users), the ALM-036 24 h window, maintenance-done cutoff, water-today midnight, telemetry retention, schedules (Milestone D) | JWT expiry, WebSocket heartbeats, **data staleness** (ALM-044 / ALM-029: about the link, not the farm), command pickup/execution **timeouts**, debounce timers, rate limits |

Rule of thumb: if it describes **what happened on the farm**, use farm time. If it describes **whether the software link is healthy**, use real time.

- Replace direct `utcnow()` calls in `services/` with `clock.farm_now()` where the table says so. Add a lint/test guard so new code can't quietly use the wrong clock.
- Telemetry sampling: one sample per **10 s of farm time**, but never more than one per real second. At 360× that's one sample per 6 farm-minutes. Store the farm timestamp.
- Debounce and timeouts stay in real seconds. They protect the software, not the farm.

### Simulator
- Reads the clock on start (`GET /api/v1/sim/clock`) and follows a new WS event `clock.changed`.
- Physics `dt = real_dt × speed`, keeping the existing sub-stepping for stability. Paused means zero physics steps, while state is still published so the UI stays live.
- **Jump:** the skipped interval is not integrated step by step. Apply a closed-form approximation instead (soil drying and tank refill over the skipped hours), and stop any running zone first, with the event logged as `clock.jumped`.
- `TIMESCALE` in `.env` becomes the *initial* speed only (default 1).

### API
- `GET /api/v1/sim/clock` → `{mode, speed, paused, farm_now, real_now}` (any user).
- `POST /api/v1/sim/clock` (admin, simulator mode only) with `{speed}` | `{pause: true}` | `{step_min: 1}` | `{jump_to: "05:30"}` | `{real: true, confirm: true}`. Each change logs a `clock.*` event and broadcasts `clock.changed`.
- `state.snapshot` and `clock.changed` include `farm_now` and `speed`, so clients can tick locally between messages.

### Web
- `useFarmClock()` hook: start from the server's `farm_now` + `speed`, tick locally, and resync on `clock.changed`. **Every** clock reads from it: header clock, map lighting (`farmNow`), seasonal sprites (`month`), chart axis labels, event times, "water today".
- **SIMULATED TIME badge** (amber, with the speed, e.g. `⏩ 60× · وقت محاكاة`) beside every clock when `mode = sim` and speed ≠ 1 or the clock is offset from real time.
- Presenter-mode header chip: pause/play, speed menu, jump-to-time, step. The Simulator page gets the full panel, including "Back to real time" (with confirm, explaining that demo history will be cleared).
- Phones: the chip collapses to the badge. The controls live on the Simulator page.

### Tests (minimum)
- Clock: speed, pause, re-anchoring, monotonic jump, persistence across restart, locked in real-PLC mode.
- ALM-036 and water-today follow farm time (e.g. 24 farm-hours at 360× clears the window).
- Staleness and command timeouts still use real time at 360×.
- Simulator: paused means no physics. 60× for 10 real seconds gives about 10 farm-minutes of tank and moisture change. A jump stops running zones.
- Web: the badge appears only in sim mode, and the clock hook resyncs on `clock.changed`.
- Live: run `normal_day` at 360× and check that charts, lighting and water-today line up.

## Out of scope
- Running backwards or replaying history.
- Sim sessions kept side by side with real history (rejected: "Back to real time" clears history instead).
- A training mode with the real PLC.
