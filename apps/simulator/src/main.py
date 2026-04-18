"""Simulator entry point."""

import asyncio
import os
import signal
import sys

from .state import FarmSimulationState
from .engine import SimulatorEngine
from .client import APIClient


async def run_simulator():
    """Wire up simulator engine and HTTP client, and run them."""
    # Obtain timescale from environment defaulting to 1x
    # Allow configuring time acceleration, e.g., TIMESCALE=60 means 1s real = 1m sim
    time_scale = float(os.getenv("TIMESCALE", "1.0"))
    
    state = FarmSimulationState()
    engine = SimulatorEngine(state, timescale=time_scale)
    
    api_url = os.getenv("API_URL", "http://127.0.0.1:8000/api/v1")
    client = APIClient(engine, base_url=api_url)
    
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
        
    for name in {'SIGINT', 'SIGTERM'}:
        try:
            loop.add_signal_handler(getattr(signal, name), lambda: shutdown_signal(name))
        except NotImplementedError:
            pass # Windows selector event loop doesn't support add_signal_handler
        
    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        pass
    finally:
        print("Simulator shutting down.")


if __name__ == "__main__":
    try:
        # Windows compatibility for signal handling requires specific event loop
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(run_simulator())
    except KeyboardInterrupt:
        pass
