"""
SQLAlchemy models — re-export all for Alembic and app use.
"""

from .base import Base
from .farm import Farm
from .zone import Zone, ZoneCombination
from .pump import Pump
from .valve import Valve
from .sensor import Sensor
from .water_source import WaterSource
from .schedule import Schedule
from .command import Command
from .alarm import Alarm
from .irrigation_cycle import IrrigationCycle
from .event_log import EventLog
from .telemetry import TelemetryPoint, DeviceStateSnapshot
from .user import User
from .ai import (
    AISuggestion,
    DetectedAnomaly,
    WeatherCache,
    WeatherAdvisory,
    AIInsight,
    MaintenancePrediction,
)

__all__ = [
    "Base",
    "Farm",
    "Zone",
    "ZoneCombination",
    "Pump",
    "Valve",
    "Sensor",
    "WaterSource",
    "Schedule",
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
