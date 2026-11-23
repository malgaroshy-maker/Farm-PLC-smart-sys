"""Controller adapter interface (Milestone G3).

The gateway (client.py) speaks to the API: it loads the farm layout, pushes live state
to /state/sync, pulls pending commands and reports their results. *What* it talks to on
the farm side is an adapter:

  - SimulatorAdapter  — the physics simulator (today's demo)
  - OpcUaAdapter      — a Siemens S7-1200/1500 over OPC UA (tag map designed in G5)

Safety rule (unchanged): the PLC owns the interlocks. Adapters only forward commands;
they never bypass or emulate PLC safety logic on the real hardware path.
"""

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class Layout:
    zones: list[dict] = field(default_factory=list)
    pumps: list[dict] = field(default_factory=list)
    valves: list[dict] = field(default_factory=list)
    sensors: list[dict] = field(default_factory=list)


class ControllerAdapter(Protocol):
    name: str

    async def start(self, layout: Layout) -> None:
        """Connect / configure for the farm layout loaded from the API."""

    async def stop(self) -> None: ...

    async def read_state(self) -> list[dict]:
        """Live state as /state/sync payloads: [{device_key, state_json, updated_at}]."""

    async def execute(self, commands: list[dict]) -> list[dict]:
        """Forward pending commands; return immediate results [{command_id, status, reason?}]."""

    async def drain_events(self) -> list[dict]:
        """Later command results (e.g. a zone reached 'running' or failed)."""

    def link_ok(self) -> bool:
        """False while the controller link is down (state is then not pushed)."""

    def on_clock(self, payload: dict) -> None:
        """Farm-clock changes from the API (simulator follows them; a PLC uses real time)."""
