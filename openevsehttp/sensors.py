"""Sensors class for OpenEVSE HTTP."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .const import BAT_LVL, BAT_RANGE, GRID, SOLAR, TTF, VOLTAGE
from .exceptions import UnsupportedFeature

if TYPE_CHECKING:
    from .client import OpenEVSE

_LOGGER = logging.getLogger(__name__)


class Sensors:
    """Handle sensor data pushing to OpenEVSE."""

    def __init__(self, evse: OpenEVSE) -> None:
        """Initialize the sensors class."""
        self._evse = evse

    async def grid_voltage(self, voltage: int | None = None) -> None:
        """Send pushed sensor data to grid voltage."""
        if not self._evse._version_check("2.9.1"):
            _LOGGER.debug("Feature not supported for older firmware.")
            raise UnsupportedFeature

        url = f"{self._evse.url}status"
        data = {}

        if voltage is not None:
            data[VOLTAGE] = voltage

        if not data:
            _LOGGER.info("No sensor data to send to device.")
        else:
            _LOGGER.debug("Posting voltage: %s", data)
            response = await self._evse.process_request(
                url=url, method="post", data=data
            )
            _LOGGER.debug("Voltage posting response: %s", response)

    async def self_production(
        self,
        grid: int | None = None,
        solar: int | None = None,
        invert: bool = True,
        voltage: int | None = None,
    ) -> None:
        """Send pushed sensor data to self-prodcution."""
        if not self._evse._version_check("2.9.1"):
            _LOGGER.debug("Feature not supported for older firmware.")
            raise UnsupportedFeature

        # Invert the sensor -import/+export
        if invert and grid is not None:
            grid = grid * -1

        url = f"{self._evse.url}status"
        data = {}

        # Prefer grid sensor data
        if grid is not None:
            data[GRID] = grid
        elif solar is not None:
            data[SOLAR] = solar
        if voltage is not None:
            data[VOLTAGE] = voltage

        if not data:
            _LOGGER.info("No sensor data to send to device.")
        else:
            _LOGGER.debug("Posting self-production: %s", data)
            response = await self._evse.process_request(
                url=url, method="post", data=data
            )
            _LOGGER.debug("Self-production response: %s", response)

    async def soc(
        self,
        battery_level: int | None = None,
        battery_range: int | None = None,
        time_to_full: int | None = None,
        voltage: int | None = None,
    ) -> None:
        """Send pushed sensor data to SOC."""
        if not self._evse._version_check("4.1.0"):
            _LOGGER.debug("Feature not supported for older firmware.")
            raise UnsupportedFeature

        url = f"{self._evse.url}status"
        data = {}

        # Build post data
        if battery_level is not None:
            data[BAT_LVL] = battery_level
        if battery_range is not None:
            data[BAT_RANGE] = battery_range
        if time_to_full is not None:
            data[TTF] = time_to_full
        if voltage is not None:
            data[VOLTAGE] = voltage

        if not data:
            _LOGGER.info("No SOC data to send to device.")
        else:
            _LOGGER.debug("Posting SOC data: %s", data)
            response = await self._evse.process_request(
                url=url, method="post", data=data
            )
            _LOGGER.debug("SOC response: %s", response)

    async def set_shaper_live_pwr(self, power: int) -> None:
        """Send pushed sensor data to shaper."""
        if not self._evse._version_check("4.0.0"):
            _LOGGER.debug("Feature not supported for older firmware.")
            raise UnsupportedFeature

        url = f"{self._evse.url}status"
        data = {"shaper_live_pwr": power}

        _LOGGER.debug("Posting shaper data: %s", data)
        response = await self._evse.process_request(url=url, method="post", data=data)
        _LOGGER.debug("Shaper response: %s", response)
