"""Guard test: prevents code in services/ from using utcnow() for farm-facing events."""

from pathlib import Path

SERVICES_DIR = Path(__file__).resolve().parents[1] / "app" / "services"


def test_guard_no_forbidden_utcnow_in_services():
    """
    SIMULATION_TIME.md §2 table rule:
    Only link-health checks (staleness, debounce, command timeouts, rate limits)
    may read real wall-clock time (`utcnow()`).
    All farm events (telemetry ts, alarm timestamps, command user-facing times,
    water-today, event log) must use `clock.farm_now()`.
    """
    # Whitelist of allowed lines that call utcnow() in services:
    allowed_patterns = {
        "alarms.py": [
            "r_now = real_now or utcnow()",  # debounce timer
            "self.staleness_conditions(snapshots, utcnow())",  # ALM-044 / ALM-029 link check
            "real_now = utcnow()",  # debounce timer
        ],
        "anomaly.py": [
            "r_now = real_now or utcnow()",  # debounce timer
        ],
        "commands.py": [
            "requested_at_real=utcnow()",  # command timeout tracking
            "now_real = utcnow()",  # command timeout tracking
        ],
        "live_state.py": [
            "((now or utcnow()) - last).total_seconds() <= settings.state_stale_after_sec",  # link staleness
            "future = utcnow() + timedelta(seconds=settings.state_stale_after_sec)",  # clock set back
        ],
        "pump_history.py": ["wall_now = utcnow()"],  # Validate the wall-clock age of run feedback.
        "realtime.py": [
            '{"type": event_type, "ts": utcnow().isoformat(), "payload": jsonable_encoder(payload)}',  # real-time WS envelope timestamp
        ],
        "telemetry.py": [
            "now_real = utcnow()",  # at most 1/s real rate limit
        ],
        "scheduler.py": [
            "now_real = utcnow()",  # tick downtime detection (real elapsed time between ticks)
        ],
        "features.py": [
            "row.updated_at = utcnow()",  # when the owner flipped a switch (real-world audit time)
        ],
        "notify.py": [
            "row.updated_at = utcnow()",  # when push keys were generated (real-world audit time)
            "s.last_ok_at = utcnow()",  # when a phone push was delivered (real-world time)
        ],
        "scenarios.py": [  # scenario runner internal execution timers
            "self._started = utcnow()",
            "self._picked_up_at = utcnow()",
            "started_at=utcnow().isoformat()",
            "self.state.log.append(f\"{utcnow().strftime('%H:%M:%S')} {message}\")",
            "self.state.finished_at = utcnow().isoformat()",
        ],
        # G7 soil probes: a reading is fresh for a real-time window (link staleness, like ALM-044)
        "soil.py": ["now = now or utcnow()"],
        # G7 backups run on the real wall clock (a demo clock jump must not skip or repeat them)
        "backup.py": [
            '"at": utcnow().isoformat(),',
            '"last_error_at": utcnow().isoformat()',
        ],
    }

    for path in SERVICES_DIR.glob("*.py"):
        filename = path.name
        content = path.read_text(encoding="utf-8")
        lines = content.splitlines()
        file_allowed = allowed_patterns.get(filename, [])
        for idx, line in enumerate(lines, start=1):
            stripped = line.strip()
            if "utcnow()" in stripped and not stripped.startswith("#"):
                allowed = any(p in stripped for p in file_allowed)
                assert allowed, (
                    f"Forbidden utcnow() call in {filename}:{idx}:\n"
                    f"  {line}\n"
                    f"Farm-facing events must use clock.farm_now() per docs/SIMULATION_TIME.md."
                )
