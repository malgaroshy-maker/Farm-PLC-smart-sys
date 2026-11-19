"""
SQLAlchemy models — re-export all for Alembic and app use.
"""

from .ai import (
    AIInsight,
    AISuggestion,
    DetectedAnomaly,
    MaintenancePrediction,
    WeatherAdvisory,
    WeatherCache,
)
from .alarm import Alarm
from .base import Base
from .clock import FarmClockModel
from .command import Command
from .event_log import EventLog
from .farm import Farm
from .irrigation_cycle import IrrigationCycle
from .program import Program, ProgramStep, SchedulerState
from .pump import Pump
from .schedule import Schedule
from .sensor import Sensor
from .telemetry import DeviceStateSnapshot, TelemetryPoint
from .user import User
from .valve import Valve
from .water_source import WaterSource
from .zone import Zone, ZoneCombination

__all__ = [
    "Base",
    "Farm",
    "FarmClockModel",
    "Zone",
    "ZoneCombination",
    "Pump",
    "Valve",
    "Sensor",
    "WaterSource",
    "Schedule",
    "Program",
    "ProgramStep",
    "SchedulerState",
    "Command",
    "Alarm",
    "IrrigationCycle",
    "EventLog",
    "TelemetryPoint",
    "DeviceStateSnapshot",
    "User",
    "AISuggestion",
    "DetectedAnomaly",
    "WeatherCache",
    "WeatherAdvisory",
    "AIInsight",
    "MaintenancePrediction",
]
