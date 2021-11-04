"""Provide a package for python-openevse-http."""
from __future__ import annotations

import asyncio
import datetime
import logging
from typing import Any, Callable, Optional

import aiohttp  # type: ignore

from .const import MAX_AMPS, MIN_AMPS
from .exceptions import AuthenticationError, ParseJSONError, UnknownError

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

ERROR_AUTH_FAILURE = "Authorization failure"
ERROR_TOO_MANY_RETRIES = "Too many retries"
ERROR_UNKNOWN = "Unknown"
ERROR_TIMEOUT = "Timeout while updating "

MAX_FAILED_ATTEMPTS = 5

SIGNAL_CONNECTION_STATE = "websocket_state"
STATE_CONNECTED = "connected"
STATE_DISCONNECTED = "disconnected"
STATE_STARTING = "starting"
STATE_STOPPED = "stopped"


class OpenEVSEWebsocket:
    """Represent a websocket connection to a OpenEVSE charger."""

    def __init__(
        self,
        server,
        callback,
        user=None,
        password=None,
    ):
        """Initialize a OpenEVSEWebsocket instance."""
        self.session = aiohttp.ClientSession()
        self.uri = self._get_uri(server)
        self._user = user
        self._password = password
        self.callback = callback
        self._state = None
        self.failed_attempts = 0
        self._error_reason = None

    @property
    def state(self):
        """Return the current state."""
        return self._state

    @state.setter
    def state(self, value):
        """Set the state."""
        self._state = value
        _LOGGER.debug("Websocket %s", value)
        self.callback(SIGNAL_CONNECTION_STATE, value, self._error_reason)
        self._error_reason = None

    @staticmethod
    def _get_uri(server):
        """Generate the websocket URI."""
        return server[: server.rfind("/")].replace("http", "ws") + "/ws"

    async def running(self):
        """Open a persistent websocket connection and act on events."""
        self.state = STATE_STARTING
        auth = None

        if self._user and self._password:
            auth = aiohttp.BasicAuth(self._user, self._password)

        try:
            async with self.session.ws_connect(
                self.uri,
                heartbeat=15,
                auth=auth,
            ) as ws_client:
                self.state = STATE_CONNECTED
                self.failed_attempts = 0

                async for message in ws_client:
                    if self.state == STATE_STOPPED:
                        break

                    if message.type == aiohttp.WSMsgType.TEXT:
                        msg = message.json()
                        msgtype = "data"
                        self.callback(msgtype, msg, None)

                    elif message.type == aiohttp.WSMsgType.CLOSED:
                        _LOGGER.warning("Websocket connection closed")
                        break

                    elif message.type == aiohttp.WSMsgType.ERROR:
                        _LOGGER.error("Websocket error")
                        break

        except aiohttp.ClientResponseError as error:
            if error.code == 401:
                _LOGGER.error("Credentials rejected: %s", error)
                self._error_reason = ERROR_AUTH_FAILURE
            else:
                _LOGGER.error("Unexpected response received: %s", error)
                self._error_reason = ERROR_UNKNOWN
            self.state = STATE_STOPPED
        except (aiohttp.ClientConnectionError, asyncio.TimeoutError) as error:
            if self.failed_attempts >= MAX_FAILED_ATTEMPTS:
                self._error_reason = ERROR_TOO_MANY_RETRIES
                self.state = STATE_STOPPED
            elif self.state != STATE_STOPPED:
                retry_delay = min(2 ** (self.failed_attempts - 1) * 30, 300)
                self.failed_attempts += 1
                _LOGGER.error(
                    "Websocket connection failed, retrying in %ds: %s",
                    retry_delay,
                    error,
                )
                self.state = STATE_DISCONNECTED
                await asyncio.sleep(retry_delay)
        except Exception as error:  # pylint: disable=broad-except
            if self.state != STATE_STOPPED:
                _LOGGER.exception("Unexpected exception occurred: %s", error)
                self._error_reason = ERROR_UNKNOWN
                self.state = STATE_STOPPED
        else:
            if self.state != STATE_STOPPED:
                self.state = STATE_DISCONNECTED
                await asyncio.sleep(5)

    async def listen(self):
        """Start the listening websocket."""
        self.failed_attempts = 0
        while self.state != STATE_STOPPED:
            await self.running()

    def close(self):
        """Close the listening websocket."""
        self.state = STATE_STOPPED


class OpenEVSE:
    """Represent an OpenEVSE charger."""

    def __init__(self, host: str, user: str = None, pwd: str = None) -> None:
        """Connect to an OpenEVSE charger equipped with wifi or ethernet."""
        self._user = user
        self._pwd = pwd
        self.url = f"http://{host}/"
        self._status: dict = {}
        self._config: dict = {}
        self._override = None
        self._ws_listening = False
        self.websocket: Optional[OpenEVSEWebsocket] = None
        self.callback: Optional[Callable] = None
        self._loop = None

    async def send_command(self, command: str) -> tuple | None:
        """Send a RAPI command to the charger and parses the response."""
        auth = None
        url = f"{self.url}r"
        data = {"json": 1, "rapi": command}

        if self._user and self._pwd:
            auth = aiohttp.BasicAuth(self._user, self._pwd)

        _LOGGER.debug("Posting data: %s to %s", command, url)
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=data, auth=auth) as resp:
                if resp.status == 400:
                    _LOGGER.debug("JSON error: %s", await resp.text())
                    raise ParseJSONError
                if resp.status == 401:
                    _LOGGER.debug("Authentication error: %s", await resp.text())
                    raise AuthenticationError

                value = await resp.json()

                if "ret" not in value:
                    return False, ""
                return value["cmd"], value["ret"]

    async def update(self) -> None:
        """Update the values."""
        auth = None
        urls = [f"{self.url}config"]

        if self._user and self._pwd:
            auth = aiohttp.BasicAuth(self._user, self._pwd)

        if not self._ws_listening:
            urls = [f"{self.url}status", f"{self.url}config"]

        async with aiohttp.ClientSession() as session:
            for url in urls:
                _LOGGER.debug("Updating data from %s", url)
                async with session.get(url, auth=auth) as resp:
                    if resp.status == 401:
                        _LOGGER.debug("Authentication error: %s", resp.text())
                        raise AuthenticationError

                    if "/status" in url:
                        try:
                            self._status = await resp.json()
                            _LOGGER.debug("Status update: %s", self._status)
                        except TimeoutError:
                            _LOGGER.error("%s status.", ERROR_TIMEOUT)
                    else:
                        try:
                            self._config = await resp.json()
                            _LOGGER.debug("Config update: %s", self._config)
                        except TimeoutError:
                            _LOGGER.error("%s config.", ERROR_TIMEOUT)

        if not self.websocket:
            # Start Websocket listening
            self.websocket = OpenEVSEWebsocket(
                self.url, self._update_status, self._user, self._pwd
            )
            if not self._ws_listening:
                self._start_listening()

    def _start_listening(self):
        """Start the websocket listener."""
        try:
            _LOGGER.debug("Attempting to find running loop...")
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            self._loop = asyncio.get_event_loop()
            _LOGGER.debug("Using new event loop...")

        if not self._ws_listening:
            self._loop.create_task(self.websocket.listen())
            pending = asyncio.all_tasks()
            self._ws_listening = True
            self._loop.run_until_complete(asyncio.gather(*pending))

    def _update_status(self, msgtype, data, error):
        """Update data from websocket listener."""
        if msgtype == SIGNAL_CONNECTION_STATE:
            if data == STATE_CONNECTED:
                _LOGGER.debug("Websocket to %s successful", self.url)
                self._ws_listening = True
            elif data == STATE_DISCONNECTED:
                _LOGGER.debug(
                    "Websocket to %s disconnected, retrying",
                    self.url,
                )
                self._ws_listening = False
            # Stopped websockets without errors are expected during shutdown
            # and ignored
            elif data == STATE_STOPPED and error:
                _LOGGER.error(
                    "Websocket to %s failed, aborting [Error: %s]",
                    self.url,
                    error,
                )
                self._ws_listening = False

        elif msgtype == "data":
            _LOGGER.debug("ws_data: %s", data)
            if "wh" in data.keys():
                data["watthour"] = data.pop("wh")
            self._status.update(data)

            if self.callback is not None:
                self.callback()

    def ws_disconnect(self) -> None:
        """Disconnect the websocket listener."""
        assert self.websocket
        self.websocket.close()
        self._ws_listening = False

    @property
    def ws_state(self) -> Any:
        """Return the status of the websocket listener."""
        assert self.websocket
        return self.websocket.state

    async def set_charge_mode(self, mode: str = "fast") -> None:
        """Set the charge mode."""
        url = f"{self.url}config"

        if mode != "fast" or mode != "eco":
            _LOGGER.error("Invalid value for charge_mode: %s", mode)
            raise ValueError

        if self._user and self._pwd:
            auth = aiohttp.BasicAuth(self._user, self._pwd)

        _LOGGER.debug("Setting charge mode to %s", mode)
        async with aiohttp.ClientSession() as session:
            async with session.post(url, auth=auth) as resp:
                message = await resp.json()
                if resp.status == 400:
                    _LOGGER.debug("JSON error: %s", message["msg"])
                    raise ParseJSONError
                elif resp.status == 401:
                    _LOGGER.debug("Authentication error: %s", message["msg"])
                    raise AuthenticationError
                elif resp.status == 404:
                    _LOGGER.error("Error getting override status: %s", message["msg"])

                if message["msg"] != "done":
                    _LOGGER.error("Problem issuing command: %s", message["msg"])
                    raise UnknownError

    async def get_override(self) -> None:
        """Get the manual override status."""
        url = f"{self.url}override"

        if self._user and self._pwd:
            auth = aiohttp.BasicAuth(self._user, self._pwd)

        _LOGGER.debug("Geting data from %s", url)
        async with aiohttp.ClientSession() as session:
            async with session.get(url, auth=auth) as resp:
                if resp.status == 400:
                    _LOGGER.debug("JSON error: %s", await resp.text())
                    raise ParseJSONError
                if resp.status == 401:
                    _LOGGER.debug("Authentication error: %s", await resp.text())
                    raise AuthenticationError
                if resp.status == 404:
                    error = await resp.json()
                    _LOGGER.error("Error getting override status: %s", error["msg"])

                value = await resp.json()
                return value

    async def set_override(
        self,
        state: str,
        charge_current: int,
        max_current: int,
        energy_limit: int,
        time_limit: int,
        auto_release: bool = True,
    ) -> str:
        """Set the manual override status."""
        url = f"{self.url}override"

        if self._user and self._pwd:
            auth = aiohttp.BasicAuth(self._user, self._pwd)

        if state not in ["active", "disabled"]:
            raise ValueError

        data = {
            "state": state,
            "charge_current": charge_current,
            "max_current": max_current,
            "energy_limit": energy_limit,
            "time_limit": time_limit,
            "auto_release": auto_release,
        }

        _LOGGER.debug("Setting override config on %s", url)
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=data, auth=auth) as resp:
                if resp.status == 400:
                    _LOGGER.debug("JSON error: %s", await resp.text())
                    raise ParseJSONError
                if resp.status == 401:
                    _LOGGER.debug("Authentication error: %s", await resp.text())
                    raise AuthenticationError

                value = await resp.json()
                _LOGGER.debug("Override set response: %s", value["msg"])
                return value

    async def toggle_override(self) -> None:
        """Toggle the manual override status."""
        url = f"{self.url}override"

        if self._user and self._pwd:
            auth = aiohttp.BasicAuth(self._user, self._pwd)

        _LOGGER.debug("Toggling manual override %s", url)
        async with aiohttp.ClientSession() as session:
            async with session.patch(url, auth=auth) as resp:
                if resp.status == 400:
                    _LOGGER.debug("JSON error: %s", await resp.text())
                    raise ParseJSONError
                if resp.status == 401:
                    _LOGGER.debug("Authentication error: %s", await resp.text())
                    raise AuthenticationError

                _LOGGER.debug("Toggle response: %s", resp.status)

    async def clear_override(self) -> None:
        """Clear the manual override status."""
        url = f"{self.url}overrride"

        if self._user and self._pwd:
            auth = aiohttp.BasicAuth(self._user, self._pwd)

        _LOGGER.debug("Clearing manual overrride %s", url)
        async with aiohttp.ClientSession() as session:
            async with session.delete(url, auth=auth) as resp:
                if resp.status == 400:
                    _LOGGER.debug("JSON error: %s", await resp.text())
                    raise ParseJSONError
                if resp.status == 401:
                    _LOGGER.debug("Authentication error: %s", await resp.text())
                    raise AuthenticationError

                _LOGGER.debug("Toggle response: %s", resp.status)

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
    def state(self) -> str:
        """Return charger's state."""
        assert self._status is not None
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
        """Return the charge current.

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
        temp = self._status["temp2"] if self._status["temp2"] else None
        if temp is not None:
            return temp / 10
        return None

    @property
    def ir_temperature(self) -> float | None:
        """Return the temperature of the IR remote sensor.

        In degrees Celcius.
        """
        assert self._status is not None
        temp = self._status["temp3"] if self._status["temp3"] else None
        if temp is not None:
            return temp / 10
        return None

    @property
    def esp_temperature(self) -> float | None:
        """Return the temperature of the ESP sensor, in degrees Celcius."""
        assert self._status is not None
        if "temp4" in self._status:
            temp = self._status["temp4"] if self._status["temp4"] else None
            if temp is not None:
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

    @property
    def vehicle(self) -> str:
        """Return if a vehicle is connected dto the EVSE."""
        assert self._status is not None
        return self._status["vehicle"]

    @property
    def ota_update(self) -> str:
        """Return if an OTA update is active."""
        assert self._status is not None
        return self._status["ota_update"]

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
