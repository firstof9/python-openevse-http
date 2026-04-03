"""Sensor data posting methods for the OpenEVSE charger."""

from __future__ import annotations

import logging
from typing import Any

from .const import BAT_LVL, BAT_RANGE, GRID, SOLAR, TTF, VOLTAGE
from .exceptions import UnsupportedFeature

_LOGGER = logging.getLogger(__name__)


class SensorsMixin:
    """Mixin providing sensor data posting methods for OpenEVSE."""

    url: str

    # These are defined in client.py
    def _version_check(self, min_version: str, max_version: str = "") -> bool:
        raise NotImplementedError

    async def process_request(
        self, url: str, method: str = "", data: Any = None, rapi: Any = None
    ) -> dict[str, str] | dict[str, Any]:
        raise NotImplementedError

    # HTTP Posting of grid voltage
    async def grid_voltage(self, voltage: int | None = None) -> None:
        """Send pushed sensor data to grid voltage."""
        if not self._version_check("2.9.1"):
            _LOGGER.debug("Feature not supported for older firmware.")
            raise UnsupportedFeature

        url = f"{self.url}status"
        data = {}

        if voltage is not None:
            data[VOLTAGE] = voltage

        if not data:
            _LOGGER.info("No sensor data to send to device.")
        else:
            _LOGGER.debug("Posting voltage: %s", data)
            response = await self.process_request(url=url, method="post", data=data)
            _LOGGER.debug("Voltage posting response: %s", response)

    # Self production HTTP Posting
    async def self_production(
        self,
        grid: int | None = None,
        solar: int | None = None,
        invert: bool = True,
        voltage: int | None = None,
    ) -> None:
        """Send pushed sensor data to self-prodcution."""
        if not self._version_check("2.9.1"):
            _LOGGER.debug("Feature not supported for older firmware.")
            raise UnsupportedFeature

        # Invert the sensor -import/+export
        if invert and grid is not None:
            grid = grid * -1

        url = f"{self.url}status"
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
            response = await self.process_request(url=url, method="post", data=data)
            _LOGGER.debug("Self-production response: %s", response)

    # State of charge HTTP posting
    async def soc(
        self,
        battery_level: int | None = None,
        battery_range: int | None = None,
        time_to_full: int | None = None,
        voltage: int | None = None,
    ) -> None:
        """Send pushed sensor data to self-prodcution."""
        if not self._version_check("4.1.0"):
            _LOGGER.debug("Feature not supported for older firmware.")
            raise UnsupportedFeature

        url = f"{self.url}status"
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
            response = await self.process_request(url=url, method="post", data=data)
            _LOGGER.debug("SOC response: %s", response)

    # Shaper HTTP Posting
    async def set_shaper_live_pwr(self, power: int) -> None:
        """Send pushed sensor data to shaper."""
        if not self._version_check("4.0.0"):
            _LOGGER.debug("Feature not supported for older firmware.")
            raise UnsupportedFeature

        url = f"{self.url}status"
        data = {"shaper_live_pwr": power}

        _LOGGER.debug("Posting shaper data: %s", data)
        response = await self.process_request(url=url, method="post", data=data)
        _LOGGER.debug("Shaper response: %s", response)
