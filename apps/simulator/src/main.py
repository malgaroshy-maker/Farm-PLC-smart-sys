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

    # Which controller is on the farm side (Milestone G3): simulator (default), opcua or modbus (G7)
    kind = os.getenv("CONTROLLER_ADAPTER", "simulator").strip().lower()
    extra_tasks = []
    if kind == "opcua":
        from .adapters.opcua_adapter import OpcUaAdapter, load_tagmap

        tagmap_path = os.getenv("OPCUA_TAGMAP", "")
        if not tagmap_path:
            raise SystemExit("CONTROLLER_ADAPTER=opcua needs OPCUA_TAGMAP=<tag map json>")
        adapter = OpcUaAdapter(load_tagmap(tagmap_path))
        client = APIClient(adapter, base_url=api_url, token=token)
        run_engine = False
    elif kind == "modbus":
        from .adapters.modbus_adapter import ModbusAdapter, load_map

        map_path = os.getenv("MODBUS_MAP", "")
        if not map_path:
            raise SystemExit("CONTROLLER_ADAPTER=modbus needs MODBUS_MAP=<register map json>")
        regmap = load_map(map_path)
        if os.getenv("MODBUS_HOST"):
            regmap["host"] = os.environ["MODBUS_HOST"]
        if os.getenv("PLCSIM_PLANT", "").strip() in ("1", "true", "yes"):
            # G5: the REAL PLC program in PLCSIM Advanced; this process plays the farm around it
            from .plcsim_plant import PlcsimGateway, plant_from_env

            _plant, runner, _bridge = plant_from_env(regmap)
            extra_tasks.append(runner.run())
            adapter = PlcsimGateway(regmap, runner)
            print(
                f"[PLANT] PLC in PLCSIM at {regmap['host']}:{regmap.get('port', 502)} (Modbus TCP)"
            )
            run_engine = False
        elif os.getenv("VIRTUAL_PLC", "").strip() in ("1", "true", "yes"):
            # G5: no PLC yet -> the simulator plays the PLC behind the same Modbus registers
            from .virtual_plc import VirtualPlantGateway, VirtualPlc

            vplc = VirtualPlc(engine, regmap)
            port = await vplc.start("127.0.0.1", int(os.getenv("VIRTUAL_PLC_PORT", "1502")))
            regmap["host"], regmap["port"] = "127.0.0.1", port
            plant = APIClient(engine, base_url=api_url, token=token, initial_timescale=time_scale)

            async def plant_loop():
                while not await plant.fetch_initial_layout():  # the farm's layout and clock
                    await asyncio.sleep(2.0)
                await plant.sync_clock()
                plant.running = True  # ws_loop only listens while running: speed/pause/jump follow
                await asyncio.gather(plant.ws_loop(), vplc.run_loop())

            extra_tasks.append(plant_loop())
            adapter = VirtualPlantGateway(regmap, engine)
            print(f"[VPLC] Virtual PLC on 127.0.0.1:{port} (Modbus TCP)")
            run_engine = True
        else:
            adapter = ModbusAdapter(regmap)
            run_engine = False
        client = APIClient(adapter, base_url=api_url, token=token)
    else:
        client = APIClient(engine, base_url=api_url, token=token, initial_timescale=time_scale)
        run_engine = True

    # Run loops concurrently
    loop = asyncio.get_running_loop()

    tasks = [loop.create_task(client.run_loop())]
    if run_engine:
        tasks.append(loop.create_task(engine.run_loop()))
    tasks += [loop.create_task(t) for t in extra_tasks]

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
