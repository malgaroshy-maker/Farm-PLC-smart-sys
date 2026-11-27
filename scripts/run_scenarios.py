"""Run every acceptance scenario against the software simulator and fail if one fails.

    python scripts/run_scenarios.py [name ...]

Starts its own API and simulator on a throwaway database, so it touches nothing on this PC.
CI runs it on every push. The same scenarios run against the real PLC program in PLCSIM by hand.
"""

import json
import os
import secrets
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "apps" / "api"
PORT = int(os.environ.get("SCENARIO_API_PORT", "8021"))
BASE = f"http://127.0.0.1:{PORT}/api/v1"
SCENARIO_TIMEOUT_S = 600


def call(method: str, path: str, token: str | None = None, body: dict | None = None):
    req = urllib.request.Request(
        BASE + path, method=method, data=json.dumps(body).encode() if body else None
    )
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read() or "null")


def until(what: str, check, seconds: float = 60):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        try:
            if result := check():
                return result
        except (urllib.error.URLError, ConnectionError, TimeoutError):
            pass
        time.sleep(1)
    raise SystemExit(f"{what} did not happen within {seconds:.0f}s")


def main() -> int:
    work = Path(tempfile.mkdtemp(prefix="farm-scenarios-"))
    password = secrets.token_urlsafe(16)
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite+aiosqlite:///{(work / 'farm.db').as_posix()}",
        "ADMIN_USERNAME": "admin",
        "ADMIN_PASSWORD": password,
        "SECRET_KEY": secrets.token_urlsafe(48),
        "SIMULATOR_TOKEN": secrets.token_urlsafe(24),
        "DEPLOYMENT_MODE": "simulation",
        "CONTROLLER_MODE": "simulator",
        "CONTROLLER_ADAPTER": "simulator",
        # no outside AI calls or alerts from a test run
        "APINEX_API_KEY": "",
        "GEMINI_API_KEY": "",
        "TELEGRAM_BOT_TOKEN": "",
        "BACKUP_DIR": str(work / "backups"),
        "API_URL": BASE,
        "API_PORT": str(PORT),
        "PYTHONIOENCODING": "utf-8",
    }
    python = sys.executable
    logs = {name: (work / f"{name}.log").open("w", encoding="utf-8") for name in ("api", "sim")}
    processes = []
    try:
        for step in (["-m", "alembic", "upgrade", "head"], ["-m", "app.seed"]):
            subprocess.run([python, *step], cwd=API, env=env, check=True, stdout=logs["api"])

        def start(name: str, args: list[str], cwd: Path) -> None:
            processes.append(
                subprocess.Popen(
                    [python, *args], cwd=cwd, env=env, stdout=logs[name], stderr=subprocess.STDOUT
                )
            )

        start("api", ["-m", "uvicorn", "app.main:app", "--port", str(PORT)], API)
        login = {"username": "admin", "password": password}
        token = until("API start", lambda: call("POST", "/auth/login", body=login))["access_token"]
        start("sim", ["-m", "src.main"], ROOT / "apps" / "simulator")
        until("live data", lambda: call("GET", "/state/map", token)["data_fresh"])

        catalog = call("GET", "/sim/scenarios", token)
        entries = catalog if isinstance(catalog, list) else catalog["scenarios"]
        names = sys.argv[1:] or [e["name"] for e in entries if not e.get("unavailable_reason")]
        failed = []
        for name in names:
            began = time.monotonic()
            run = call("POST", f"/sim/scenarios/{name}/run", token, {})
            while run["status"] == "running":
                if time.monotonic() - began > SCENARIO_TIMEOUT_S:
                    run = {**run, "status": "timed out"}
                    break
                time.sleep(2)
                state = call("GET", "/sim/scenarios", token)
                run = state.get("run", run) if isinstance(state, dict) else run
            ok = run["status"] == "passed"
            print(f"{'PASS' if ok else 'FAIL'}  {name}  {time.monotonic() - began:.0f}s", flush=True)
            if not ok:
                failed.append(name)
                print("\n".join(run.get("log", [])[-12:]), run.get("message", ""), flush=True)
        print(f"{len(names) - len(failed)}/{len(names)} scenarios passed")
        return 1 if failed or not names else 0
    finally:
        for process in reversed(processes):
            process.terminate()
        for process in processes:
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
        for log in logs.values():
            log.close()
        print(f"logs: {work}")


if __name__ == "__main__":
    sys.exit(main())
