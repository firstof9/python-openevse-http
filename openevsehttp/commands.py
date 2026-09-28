"""Commands mixin for OpenEVSE HTTP client."""

from __future__ import annotations

from .commands_base import BaseCommandMixin
from .commands_core import CoreCommandsMixin
from .commands_diagnostics import DiagnosticsCommandsMixin
from .commands_firmware import FirmwareCommandsMixin
from .commands_schedule import ScheduleCommandsMixin
from .commands_security import SecurityCommandsMixin
from .commands_time import TimeCommandsMixin

__all__ = [
    "BaseCommandMixin",
    "CommandsMixin",
    "CoreCommandsMixin",
    "DiagnosticsCommandsMixin",
    "FirmwareCommandsMixin",
    "ScheduleCommandsMixin",
    "SecurityCommandsMixin",
    "TimeCommandsMixin",
]


class CommandsMixin(
    CoreCommandsMixin,
    FirmwareCommandsMixin,
    ScheduleCommandsMixin,
    SecurityCommandsMixin,
    DiagnosticsCommandsMixin,
    TimeCommandsMixin,
):
    """Composite mixin providing all command methods for OpenEVSE."""
