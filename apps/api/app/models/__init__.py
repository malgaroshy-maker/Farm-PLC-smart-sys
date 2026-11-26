"""
SQLAlchemy models — re-export all for Alembic and app use.
"""

from .ai import (
    AIBriefing,
    AICallLog,
    AIInsight,
    AISettings,
    AISuggestion,
    DetectedAnomaly,
    MaintenancePrediction,
    ProgramOverride,
    WeatherAdvisory,
    WeatherCache,
)
from .alarm import Alarm
from .base import Base
from .clock import FarmClockModel
from .command import Command
from .event_log import EventLog
from .farm import Farm
from .feature_flag import FeatureFlag
from .irrigation_cycle import IrrigationCycle
from .notification import NotificationSettings, PushSubscription
from .program import Program, ProgramStep, SchedulerState
from .pump import Pump, PumpObservationSpan
from .schedule import Schedule
from .sensor import Sensor
from .soil import CropMoistureLevel
from .telemetry import DeviceStateSnapshot, TelemetryPoint
from .user import User
from .valve import Valve
from .water_source import WaterSource
from .zone import Zone, ZoneCombination

__all__ = [
    "NotificationSettings",
    "PushSubscription",
    "FeatureFlag",
    "CropMoistureLevel",
    "AICallLog",
    "Base",
    "Farm",
    "FarmClockModel",
    "Zone",
    "ZoneCombination",
    "Pump",
    "PumpObservationSpan",
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
    "ProgramOverride",
    "AIBriefing",
    "AISettings",
]
