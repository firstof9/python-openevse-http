from __future__ import annotations
import asyncio
import aiohttp
import datetime
import logging

from typing import Optional
from .const import MAX_AMPS, MIN_AMPS, USER_AGENT

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
    pass


class ParseJSONError(Exception):
    pass


class OpenEVSE:
    def __init__(self, host: str, username: str = None, password: str = None) -> None:
        """A connection to an OpenEVSE charger equipped with a wifi or ethernet kit."""
        self._username = username
        self._password = password
        self._url = f"http://{host}"
        self._status = None
        self._config = None
        asyncio.run(self.async_update(mode="status"))
        asyncio.run(self.async_update(mode="config"))

    async def send_command(self, command: str, cmd_type: str) -> bool:
        """Sends a command via HTTP to the charger and prases the response."""
        url = f"{self._url}/{cmd_type}"
        headers = {"User-Agent": USER_AGENT, "Accept": "application/ld+json"}
        login = None

        if self._username is not None:
            login = aiohttp.BasicAuth(self._username, self._password)

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, auth=login) as r:
                _LOGGER.debug("Posting data: %s to %s", command, url)
                if r.status == 200:
                    return True
                elif r.status == 400:
                    raise ParseJSONError
                elif r.status == 401:
                    raise AuthenticationError
                return False

    async def async_update(self, mode: str) -> None:
        url = f"{self._url}/{mode}"
        headers = {"User-Agent": USER_AGENT, "Accept": "application/ld+json"}
        login = None

        if self._username is not None:
            login = aiohttp.BasicAuth(self._username, self._password)

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, auth=login) as r:
                _LOGGER.debug("Updating data from %s", url)
                if r.status == 200:
                    value = await r.json()
                    self.update_state(mode, value)
                elif r.status == 401:
                    raise AuthenticationError

    def update_state(self, mode: str, value: dict) -> None:
        """Update cached values"""
        if mode == "status":
            self._status = value
        elif mode == "config":
            self._config = value

    @property
    def hostname(self) -> str:
        """Returns charger hostname"""
        return self._config["hostname"]

    @property
    def wifi_ssid(self) -> str:
        """Returns charger connected SSID"""
        return self._config["ssid"]

    @property
    def ammeter_offset(self) -> int:
        """Returns ammeter's current offset"""
        return self._config["offset"]

    @property
    def ammeter_scale_factor(self) -> int:
        """Returns ammeter's current scale factor"""
        return self._config["scale"]

    @property
    def temp_check_enabled(self) -> bool:
        """Returns True if enabled, False if disabled"""
        return bool(self._config["tempt"])

    @property
    def diode_check_enabled(self) -> bool:
        """Returns True if enabled, False if disabled"""
        return bool(self._config["diodet"])

    @property
    def vent_required_enabled(self) -> bool:
        """Returns True if enabled, False if disabled"""
        return bool(self._config["ventt"])

    @property
    def ground_check_enabled(self) -> bool:
        """Returns True if enabled, False if disabled"""
        return bool(self._config["groundt"])

    @property
    def stuck_relay_check_enabled(self) -> bool:
        """Returns True if enabled, False if disabled"""
        return bool(self._config["relayt"])

    @property
    def service_level(self) -> str:
        """Returns the service level"""
        return self._config["service"]

    @property
    def openevse_firmware(self) -> str:
        """Returns the firmware version"""
        return self._config["firmware"]

    @property
    def wifi_firmware(self) -> str:
        """Returns the ESP firmware version"""
        return self._config["version"]

    @property
    def ip_address(self) -> str:
        """Returns the ip address"""
        return self._status["ipaddress"]

    @property
    def charging_voltage(self) -> int:
        """Returns the charging voltage"""
        return self._status["voltage"]

    @property
    def mode(self) -> str:
        """Returns the mode"""
        return self._status["mode"]

    @property
    def using_ethernet(self) -> bool:
        """Returns True if enabled, False if disabled"""
        if "eth_connected" in self._status:
            return bool(self._status["eth_connected"])
        return False

    @property
    def stuck_relay_trip_count(self) -> int:
        """Returns the stuck relay count"""
        return self._status["stuckcount"]

    @property
    def no_gnd_trip_count(self) -> int:
        """Returns the no ground count"""
        return self._status["nogndcount"]

    @property
    def gfi_trip_count(self) -> int:
        """Returns the GFCI count"""
        return self._status["gfcicount"]

    @property
    def status(self) -> str:
        """Return charger's state"""
        if "status" in self._status:
            return self._status["status"]
        return states[int(self._status["state"])]

    @property
    def charge_time_elapsed(self) -> int:
        return self._status["elapsed"]

    @property
    def wifi_signal(self) -> str:
        """Return charger's wifi signal"""
        return self._status["srssi"]

    @property
    def charging_current(self) -> float:
        """Returns the charge time elapsed (in seconds), or 0 if is not currently charging"""
        return self._status["amp"]

    @property
    def current_capacity(self) -> int:
        """Returns the current capacity"""
        return self._status["pilot"]

    @property
    def usage_total(self) -> float:
        """Returns the total energy usage in Wh"""
        return self._status["watthour"]

    @property
    def ambient_temperature(self) -> float | None:
        """Returns the temperature of the ambient sensor, in degrees Celcius"""
        temp = None
        if "temp" in self._status and self._status["temp"]:
            temp = self._status["temp"] / 10
        else:
            temp = self._status["temp1"] / 10
        return temp

    @property
    def rtc_temperature(self) -> float | None:
        """Returns the temperature of the real time clock sensor, in degrees Celcius"""
        temp = self._status["temp2"]
        if temp != "false":
            return temp / 10
        return None

    @property
    def ir_temperature(self) -> float | None:
        """Returns the temperature of the IR remote sensor, in degrees Celcius"""
        temp = self._status["temp3"]
        if temp != "false":
            return temp / 10
        return None

    @property
    def esp_temperature(self) -> float | None:
        """Returns the temperature of the ESP sensor, in degrees Celcius"""
        if "temp4" in self._status:
            temp = self._status["temp4"]
            if temp != "false":
                return temp / 10
        return None

    @property
    def time(self) -> Optional[datetime.datetime]:
        """Get the RTC time"""
        return self._status["time"]

    @property
    def usage_session(self) -> float:
        """Get the energy usage for the current charging session.  Returns the energy usage in Wh"""
        return float(self._status["wattsec"] / 3600)

    @property
    def protocol_version(self) -> str:
        """Returns the protocol version"""
        return self._status["protocol"]

    # There is currently no min/max amps JSON data available via HTTP API methods
    @property
    def min_amps(self) -> int:
        """Returns the minimum amps"""
        return MIN_AMPS

    @property
    def max_amps(self) -> int:
        """Returns the maximum amps"""
        return MAX_AMPS
