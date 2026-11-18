"""Simulator entry point."""

import asyncio
import os
import signal
import sys
from pathlib import Path

from .client import APIClient
from .engine import SimulatorEngine
from .state import FarmSimulationState


def load_root_env() -> None:
    """Read the repo-root .env (KEY=VALUE lines) without overriding real env vars."""
    path = Path(__file__).resolve().parents[3] / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.split(" #", 1)[0].strip().strip('"').strip("'")
        os.environ.setdefault(key.strip(), value)


async def run_simulator():
    """Wire up simulator engine and HTTP client, and run them."""
    # Obtain timescale from environment defaulting to 1x
    # Allow configuring time acceleration, e.g., TIMESCALE=60 means 1s real = 1m sim
    time_scale = float(os.getenv("TIMESCALE", "1.0"))

    state = FarmSimulationState()
    engine = SimulatorEngine(state, timescale=time_scale)

    api_url = os.getenv("API_URL", "http://127.0.0.1:8000/api/v1")
    token = os.getenv("SIMULATOR_TOKEN", "dev-simulator-token")
    client = APIClient(engine, base_url=api_url, token=token, initial_timescale=time_scale)

    # Run loops concurrently
    loop = asyncio.get_running_loop()

    tasks = [
        loop.create_task(engine.run_loop()),
        loop.create_task(client.run_loop()),
    ]

    def shutdown_signal(sig):
        print(f"Received exit signal {sig}...")
        engine.running = False
        client.running = False

    for name in {"SIGINT", "SIGTERM"}:
        try:
            loop.add_signal_handler(getattr(signal, name), lambda n=name: shutdown_signal(n))
        except NotImplementedError:
            pass  # Windows selector event loop doesn't support add_signal_handler

    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        pass
    finally:
        print("Simulator shutting down.")


if __name__ == "__main__":
    load_root_env()
    try:
        # Windows compatibility for signal handling requires specific event loop
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(run_simulator())
    except KeyboardInterrupt:
        pass
