"""Provide a package for python-openevse-http."""
from __future__ import annotations

import datetime
import logging
from typing import Optional, Dict, Any

import requests

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
    def __init__(self, host: str, username: str = None, password: str = None) -> None:
        """A connection to an OpenEVSE charger equipped with a wifi or ethernet kit."""
        self._username = username
        self._password = password
        self._url = f"http://{host}"
        self._status = self.update(mode="status")
        self._config = self.update(mode="config")

    async def send_command(self, command: str, cmd_type: str) -> dict | None:
        """Sends a command via HTTP to the charger and prases the response."""
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

    def update(self, mode: str) -> dict | None:
        """Updates the values."""
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
    def hostname(self) -> Optional[Dict[Any, Any]]:
        """Return charger hostname."""
        return self._config["hostname"]

    @property
    def wifi_ssid(self) -> Optional[Dict[Any, Any]]:
        """Return charger connected SSID."""
        return self._config["ssid"]

    @property
    def ammeter_offset(self) -> Optional[Dict[Any, Any]]:
        """Return ammeter's current offset."""
        return self._config["offset"]

    @property
    def ammeter_scale_factor(self) -> Optional[Dict[Any, Any]]:
        """Return ammeter's current scale factor."""
        return self._config["scale"]

    @property
    def temp_check_enabled(self) -> Optional[Dict[Any, Any]]:
        """Return True if enabled, False if disabled."""
        return bool(self._config["tempt"])

    @property
    def diode_check_enabled(self) -> Optional[Dict[Any, Any]]:
        """Return True if enabled, False if disabled."""
        return bool(self._config["diodet"])

    @property
    def vent_required_enabled(self) -> Optional[Dict[Any, Any]]:
        """Return True if enabled, False if disabled."""
        return bool(self._config["ventt"])

    @property
    def ground_check_enabled(self) -> Optional[Dict[Any, Any]]:
        """Return True if enabled, False if disabled."""
        return bool(self._config["groundt"])

    @property
    def stuck_relay_check_enabled(self) -> Optional[Dict[Any, Any]]:
        """Return True if enabled, False if disabled."""
        return bool(self._config["relayt"])

    @property
    def service_level(self) -> Optional[Dict[Any, Any]]:
        """Return the service level."""
        return self._config["service"]

    @property
    def openevse_firmware(self) -> Optional[Dict[Any, Any]]:
        """Return the firmware version."""
        return self._config["firmware"]

    @property
    def wifi_firmware(self) -> Optional[Dict[Any, Any]]:
        """Return the ESP firmware version."""
        return self._config["version"]

    @property
    def ip_address(self) -> Optional[Dict[Any, Any]]:
        """Return the ip address."""
        return self._status["ipaddress"]

    @property
    def charging_voltage(self) -> Optional[Dict[Any, Any]]:
        """Returns the charging voltage."""
        return self._status["voltage"]

    @property
    def mode(self) -> Optional[Dict[Any, Any]]:
        """Return the mode."""
        return self._status["mode"]

    @property
    def using_ethernet(self) -> Optional[Dict[Any, Any]]:
        """Return True if enabled, False if disabled."""
        if "eth_connected" in self._status:
            return bool(self._status["eth_connected"])
        return False

    @property
    def stuck_relay_trip_count(self) -> Optional[Dict[Any, Any]]:
        """Return the stuck relay count."""
        return self._status["stuckcount"]

    @property
    def no_gnd_trip_count(self) -> Optional[Dict[Any, Any]]:
        """Return the no ground count"""
        return self._status["nogndcount"]

    @property
    def gfi_trip_count(self) -> Optional[Dict[Any, Any]]:
        """Return the GFCI count."""
        return self._status["gfcicount"]

    @property
    def status(self) -> Optional[Dict[Any, Any]]:
        """Return charger's state."""
        if "status" in self._status:
            return self._status["status"]
        return states[int(self._status["state"])]

    @property
    def charge_time_elapsed(self) -> Optional[Dict[Any, Any]]:
        """Return elapsed charging time."""
        return self._status["elapsed"]

    @property
    def wifi_signal(self) -> Optional[Dict[Any, Any]]:
        """Return charger's wifi signal."""
        return self._status["srssi"]

    @property
    def charging_current(self) -> Optional[Dict[Any, Any]]:
        """Return the charge time elapsed (in seconds), or 0 if is not currently charging."""
        return self._status["amp"]

    @property
    def current_capacity(self) -> Optional[Dict[Any, Any]]:
        """Return the current capacity."""
        return self._status["pilot"]

    @property
    def usage_total(self) -> Optional[Dict[Any, Any]]:
        """Return the total energy usage in Wh."""
        return self._status["watthour"]

    @property
    def ambient_temperature(self) -> Optional[Dict[Any, Any]] | None:
        """Return the temperature of the ambient sensor, in degrees Celcius."""
        temp = None
        if "temp" in self._status and self._status["temp"]:
            temp = self._status["temp"] / 10
        else:
            temp = self._status["temp1"] / 10
        return temp

    @property
    def rtc_temperature(self) -> Optional[Dict[Any, Any]] | None:
        """Return the temperature of the real time clock sensor, in degrees Celcius."""
        temp = self._status["temp2"]
        if temp != "0.0":
            return temp / 10
        return None

    @property
    def ir_temperature(self) -> Optional[Dict[Any, Any]] | None:
        """Return the temperature of the IR remote sensor, in degrees Celcius."""
        temp = self._status["temp3"]
        if temp != 0.0:
            return temp / 10
        return None

    @property
    def esp_temperature(self) -> Optional[Dict[Any, Any]] | None:
        """Return the temperature of the ESP sensor, in degrees Celcius."""
        if "temp4" in self._status:
            temp = self._status["temp4"]
            if temp != 0.0:
                return temp / 10
        return None

    @property
    def time(self) -> Optional[datetime.datetime]:
        """Get the RTC time."""
        return self._status["time"]

    @property
    def usage_session(self) -> Optional[Dict[Any, Any]]:
        """Get the energy usage for the current charging session.  Returns the energy usage in Wh."""
        return float(round(self._status["wattsec"] / 3600, 2))

    @property
    def protocol_version(self) -> Optional[Dict[Any, Any]]:
        """Return the protocol version."""
        return self._config["protocol"]

    # There is currently no min/max amps JSON data available via HTTP API methods
    @property
    def min_amps(self) -> Optional[Dict[Any, Any]]:
        """Return the minimum amps."""
        return MIN_AMPS

    @property
    def max_amps(self) -> Optional[Dict[Any, Any]]:
        """Return the maximum amps."""
        return MAX_AMPS
