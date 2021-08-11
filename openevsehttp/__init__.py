"""Provide a package for python-openevse-http."""
from __future__ import annotations

import datetime
import logging
from typing import Optional, Dict, Any

import requests  # type: ignore

from .const import MAX_AMPS, MIN_AMPS

_LOGGER = logging.getLogger(__name__)

states = {
    0: "unknown",
    1: "not connected",
    2: "connected",
    3: "charging",
    4: "vent required",
    5: "diode check failed",
    6: "gfci fault",
    7: "no ground",
    8: "stuck relay",
    9: "gfci self-test failure",
    10: "over temperature",
    254: "sleeping",
    255: "disabled",
}


class AuthenticationError(Exception):
    """Exception for authentication errors."""


class ParseJSONError(Exception):
    """Exception for JSON parsing errors."""


class OpenEVSE:
    """Represent an OpenEVSE charger."""

    def __init__(self, host: str, user: str = None, pwd: str = None) -> None:
        """Connect to an OpenEVSE charger equipped with a wifi or ethernet."""
        self._username = user
        self._password = pwd
        self._url = f"http://{host}"
        self._status = self.update(mode="status")
        self._config = self.update(mode="config")

    async def send_command(
        self, command: str, cmd_type: str
    ) -> Optional[Dict[Any, Any]] | None:
        """Send a command via HTTP to the charger and prases the response."""
        url = f"{self._url}/{cmd_type}"

        _LOGGER.debug("Posting data: %s to %s", command, url)
        if self._username is not None:
            value = requests.get(url, auth=(self._username, self._password))
        else:
            value = requests.get(url)

        if value.status_code == 400:
            raise ParseJSONError
        if value.status_code == 401:
            raise AuthenticationError
        return value.json()

    def update(self, mode: str) -> Optional[Dict[Any, Any]] | None:
        """Update the values."""
        url = f"{self._url}/{mode}"

        _LOGGER.debug("Updating data from %s", url)
        if self._username is not None:
            value = requests.get(url, auth=(self._username, self._password))
        else:
            value = requests.get(url)

        if value.status_code == 401:
            raise AuthenticationError
        return value.json()

    @property
    def hostname(self) -> str:
        """Return charger hostname."""
        assert self._config is not None
        return self._config["hostname"]

    @property
    def wifi_ssid(self) -> str:
        """Return charger connected SSID."""
        assert self._config is not None
        return self._config["ssid"]

    @property
    def ammeter_offset(self) -> int:
        """Return ammeter's current offset."""
        assert self._config is not None
        return self._config["offset"]

    @property
    def ammeter_scale_factor(self) -> int:
        """Return ammeter's current scale factor."""
        assert self._config is not None
        return self._config["scale"]

    @property
    def temp_check_enabled(self) -> bool:
        """Return True if enabled, False if disabled."""
        assert self._config is not None
        return bool(self._config["tempt"])

    @property
    def diode_check_enabled(self) -> bool:
        """Return True if enabled, False if disabled."""
        assert self._config is not None
        return bool(self._config["diodet"])

    @property
    def vent_required_enabled(self) -> bool:
        """Return True if enabled, False if disabled."""
        assert self._config is not None
        return bool(self._config["ventt"])

    @property
    def ground_check_enabled(self) -> bool:
        """Return True if enabled, False if disabled."""
        assert self._config is not None
        return bool(self._config["groundt"])

    @property
    def stuck_relay_check_enabled(self) -> bool:
        """Return True if enabled, False if disabled."""
        assert self._config is not None
        return bool(self._config["relayt"])

    @property
    def service_level(self) -> str:
        """Return the service level."""
        assert self._config is not None
        return self._config["service"]

    @property
    def openevse_firmware(self) -> str:
        """Return the firmware version."""
        assert self._config is not None
        return self._config["firmware"]

    @property
    def wifi_firmware(self) -> str:
        """Return the ESP firmware version."""
        assert self._config is not None
        return self._config["version"]

    @property
    def ip_address(self) -> str:
        """Return the ip address."""
        assert self._status is not None
        return self._status["ipaddress"]

    @property
    def charging_voltage(self) -> int:
        """Return the charging voltage."""
        assert self._status is not None
        return self._status["voltage"]

    @property
    def mode(self) -> str:
        """Return the mode."""
        assert self._status is not None
        return self._status["mode"]

    @property
    def using_ethernet(self) -> bool:
        """Return True if enabled, False if disabled."""
        assert self._status is not None
        if "eth_connected" in self._status:
            return bool(self._status["eth_connected"])
        return False

    @property
    def stuck_relay_trip_count(self) -> int:
        """Return the stuck relay count."""
        assert self._status is not None
        return self._status["stuckcount"]

    @property
    def no_gnd_trip_count(self) -> int:
        """Return the no ground count."""
        assert self._status is not None
        return self._status["nogndcount"]

    @property
    def gfi_trip_count(self) -> int:
        """Return the GFCI count."""
        assert self._status is not None
        return self._status["gfcicount"]

    @property
    def status(self) -> str:
        """Return charger's state."""
        assert self._status is not None
        if "status" in self._status:
            return self._status["status"]
        return states[int(self._status["state"])]

    @property
    def charge_time_elapsed(self) -> int:
        """Return elapsed charging time."""
        assert self._status is not None
        return self._status["elapsed"]

    @property
    def wifi_signal(self) -> str:
        """Return charger's wifi signal."""
        assert self._status is not None
        return self._status["srssi"]

    @property
    def charging_current(self) -> float:
        """Return the charge time elapsed (in seconds).

        0 if is not currently charging.
        """
        assert self._status is not None
        return self._status["amp"]

    @property
    def current_capacity(self) -> int:
        """Return the current capacity."""
        assert self._status is not None
        return self._status["pilot"]

    @property
    def usage_total(self) -> float:
        """Return the total energy usage in Wh."""
        assert self._status is not None
        return self._status["watthour"]

    @property
    def ambient_temperature(self) -> float | None:
        """Return the temperature of the ambient sensor, in degrees Celcius."""
        assert self._status is not None
        temp = None
        if "temp" in self._status and self._status["temp"]:
            temp = self._status["temp"] / 10
        else:
            temp = self._status["temp1"] / 10
        return temp

    @property
    def rtc_temperature(self) -> float | None:
        """Return the temperature of the real time clock sensor.

        In degrees Celcius.
        """
        assert self._status is not None
        temp = self._status["temp2"]
        if temp != "0.0":
            return temp / 10
        return None

    @property
    def ir_temperature(self) -> float | None:
        """Return the temperature of the IR remote sensor.

        In degrees Celcius.
        """
        assert self._status is not None
        temp = self._status["temp3"]
        if temp != 0.0:
            return temp / 10
        return None

    @property
    def esp_temperature(self) -> float | None:
        """Return the temperature of the ESP sensor, in degrees Celcius."""
        assert self._status is not None
        if "temp4" in self._status:
            temp = self._status["temp4"]
            if temp != 0.0:
                return temp / 10
        return None

    @property
    def time(self) -> Optional[datetime.datetime]:
        """Get the RTC time."""
        assert self._status is not None
        if "time" in self._status:
            return self._status["time"]
        return None

    @property
    def usage_session(self) -> float:
        """Get the energy usage for the current charging session.

        Return the energy usage in Wh.
        """
        assert self._status is not None
        return float(round(self._status["wattsec"] / 3600, 2))

    @property
    def protocol_version(self) -> str:
        """Return the protocol version."""
        assert self._config is not None
        return self._config["protocol"]

    # There is currently no min/max amps JSON data
    # available via HTTP API methods
    @property
    def min_amps(self) -> int:
        """Return the minimum amps."""
        return MIN_AMPS

    @property
    def max_amps(self) -> int:
        """Return the maximum amps."""
        return MAX_AMPS
