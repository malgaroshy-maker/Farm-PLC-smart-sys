"""
Domain vocabularies mirrored from packages/contracts/src/enums.ts.

tests/test_contracts_sync.py fails if these drift from the TypeScript source,
so update both sides together.
"""

from typing import Literal, get_args

SystemMode = Literal["off", "auto", "manual", "maintenance"]
UserRole = Literal["owner_admin", "operator", "viewer"]
ActorType = Literal["user", "system", "scheduler", "plc", "ai"]
CommandType = Literal[
    "start_zone",
    "stop_zone",
    "stop_all",
    "set_mode",
    "ack_alarm",
    "reset_alarm",
    "force_valve",
    "source_override",
    "inject_fault",
    "set_panel",
]
CommandStatus = Literal[
    "pending", "accepted", "rejected", "executing", "completed", "failed", "timed_out"
]
ZoneState = Literal[
    "off",
    "queued",
    "starting_pump",
    "opening_valve",
    "validating_flow",
    "running",
    "stopping",
    "completed",
    "warning",
    "faulted",
    "interrupted",
]
CycleOutcome = Literal[
    "completed",
    "aborted",
    "faulted",
    "manual_stop",
    "skipped",
]

SYSTEM_MODES: tuple[str, ...] = get_args(SystemMode)
USER_ROLES: tuple[str, ...] = get_args(UserRole)
COMMAND_TYPES: tuple[str, ...] = get_args(CommandType)
COMMAND_STATUSES: tuple[str, ...] = get_args(CommandStatus)
ZONE_STATES: tuple[str, ...] = get_args(ZoneState)
CYCLE_OUTCOMES: tuple[str, ...] = get_args(CycleOutcome)

TERMINAL_COMMAND_STATUSES = frozenset({"rejected", "completed", "failed", "timed_out"})
# Zone states that occupy hydraulic capacity.
ACTIVE_ZONE_STATES = frozenset(
    {"queued", "starting_pump", "opening_valve", "validating_flow", "running", "warning"}
)

# Which roles may issue which command types (PRD §6).
COMMAND_PERMISSIONS: dict[str, frozenset[str]] = {
    "start_zone": frozenset({"owner_admin", "operator"}),
    "stop_zone": frozenset({"owner_admin", "operator"}),
    "stop_all": frozenset({"owner_admin", "operator"}),
    "set_mode": frozenset({"owner_admin"}),
    "inject_fault": frozenset({"owner_admin"}),
    "set_panel": frozenset({"owner_admin"}),
    # G5: the Alarm Center reset also resets the controller (PLC latches, beacon, HMI)
    "reset_alarm": frozenset({"owner_admin"}),
}
# Known command types that have no implementation yet.
NOT_IMPLEMENTED_COMMANDS = frozenset({"ack_alarm", "force_valve", "source_override"})
# Alarms the controller itself holds until it gets a reset (a PLC latches a failed pump start
# and the dry-run lock-out): the app may send that reset while the alarm is still active.
CONTROLLER_LATCHED_ALARMS = frozenset({"ALM-006", "ALM-007", "ALM-027"})
