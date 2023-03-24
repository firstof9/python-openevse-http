"""Main librbary functions for python-openevse-http."""
from __future__ import annotations

import asyncio
import datetime
import json
import logging
from typing import Any, Callable, Dict, Union

import aiohttp  # type: ignore
from aiohttp.client_exceptions import ContentTypeError, ServerTimeoutError
from awesomeversion import AwesomeVersion

from .const import MAX_AMPS, MIN_AMPS
from .exceptions import (
    AlreadyListening,
    AuthenticationError,
    MissingMethod,
    MissingSerial,
    ParseJSONError,
    UnknownError,
    UnsupportedFeature,
)
from .websocket import (
    SIGNAL_CONNECTION_STATE,
    STATE_CONNECTED,
    STATE_DISCONNECTED,
    STATE_STOPPED,
    OpenEVSEWebsocket,
)

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

ERROR_TIMEOUT = "Timeout while updating"
INFO_LOOP_RUNNING = "Event loop already running, not creating new one."
UPDATE_TRIGGERS = [
    "config_version",
    "claims_version",
    "override_version",
    "schedule_version",
    "schedule_plan_version",
    "limit_version",
]


class OpenEVSE:
    """Represent an OpenEVSE charger."""

    def __init__(self, host: str, user: str = "", pwd: str = "") -> None:
        """Connect to an OpenEVSE charger equipped with wifi or ethernet."""
        self._user = user
        self._pwd = pwd
        self.url = f"http://{host}/"
        self._status: dict = {}
        self._config: dict = {}
        self._override = None
        self._ws_listening = False
        self.websocket: OpenEVSEWebsocket | None = None
        self.callback: Callable | None = None
        self._loop = None

    async def process_request(
        self,
        url: str,
        method: str = "",
        data: Any = None,
        rapi: Any = None,
    ) -> dict[str, str] | dict[str, Any]:
        """Return result of processed HTTP request."""
        auth = None
        if method is None:
            raise MissingMethod

        if self._user and self._pwd:
            auth = aiohttp.BasicAuth(self._user, self._pwd)

        async with aiohttp.ClientSession() as session:
            http_method = getattr(session, method)
            _LOGGER.debug(
                "Connecting to %s with data: %s rapi: %s using method %s",
                url,
                data,
                rapi,
                method,
            )
            try:
                async with http_method(
                    url,
                    data=rapi,
                    json=data,
                    auth=auth,
                ) as resp:
                    try:
                        message = await resp.text()
                    except UnicodeDecodeError:
                        _LOGGER.debug("Decoding error")
                        message = await resp.read()
                        message = message.decode(errors="replace")

                    try:
                        message = json.loads(message)
                    except ValueError:
                        _LOGGER.warning("Non JSON response: %s", message)

                    if resp.status == 400:
                        _LOGGER.error("Error 400: %s", message["msg"])
                        raise ParseJSONError
                    if resp.status == 401:
                        _LOGGER.error("Authentication error: %s", message)
                        raise AuthenticationError
                    if resp.status in [404, 405, 500]:
                        _LOGGER.error("%s", message)

                    if method == "post" and "config_version" in message:
                        await self.update()
                    return message

            except (TimeoutError, ServerTimeoutError):
                _LOGGER.error("%s: %s", ERROR_TIMEOUT, url)
                message = {"msg": ERROR_TIMEOUT}
            except ContentTypeError as err:
                _LOGGER.error("%s", err)
                message = {"msg": err}

            await session.close()
            return message

    async def send_command(self, command: str) -> tuple:
        """Send a RAPI command to the charger and parses the response."""
        url = f"{self.url}r"
        data = {"json": 1, "rapi": command}

        _LOGGER.debug("Posting data: %s to %s", command, url)
        value = await self.process_request(url=url, method="post", rapi=data)
        if "ret" not in value:
            if "msg" in value:
                return False, value["msg"]
            return False, ""
        return (value["cmd"], value["ret"])

    async def update(self) -> None:
        """Update the values."""
        # TODO: add addiontal endpoints to update
        urls = [f"{self.url}config"]

        if not self._ws_listening:
            urls = [f"{self.url}status", f"{self.url}config"]

        for url in urls:
            _LOGGER.debug("Updating data from %s", url)
            response = await self.process_request(url, method="get")
            if "/status" in url:
                self._status = response
                _LOGGER.debug("Status update: %s", self._status)

            else:
                self._config = response
                _LOGGER.debug("Config update: %s", self._config)

        if not self.websocket:
            # Start Websocket listening
            self.websocket = OpenEVSEWebsocket(
                self.url, self._update_status, self._user, self._pwd
            )

    async def test_and_get(self) -> dict:
        """Test connection.

        Return model serial number as dict
        """
        url = f"{self.url}config"
        data = {}

        response = await self.process_request(url, method="get")
        if "wifi_serial" in response:
            serial = response["wifi_serial"]
        else:
            _LOGGER.debug("Older firmware detected, missing serial.")
            raise MissingSerial
        if "buildenv" in response:
            model = response["buildenv"]
        else:
            model = "unknown"

        data = {"serial": serial, "model": model}
        return data

    def ws_start(self) -> None:
        """Start the websocket listener."""
        if self._ws_listening:
            raise AlreadyListening
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
            try:
                self._loop.run_until_complete(asyncio.gather(*pending))
            except RuntimeError:
                _LOGGER.info(INFO_LOOP_RUNNING)

    async def _update_status(self, msgtype, data, error):
        """Update data from websocket listener."""
        if msgtype == SIGNAL_CONNECTION_STATE:
            if data == STATE_CONNECTED:
                _LOGGER.debug("Websocket to %s successful", self.websocket.uri)
                self._ws_listening = True
            elif data == STATE_DISCONNECTED:
                _LOGGER.debug(
                    "Websocket to %s disconnected, retrying",
                    self.websocket.uri,
                )
                self._ws_listening = False
            # Stopped websockets without errors are expected during shutdown
            # and ignored
            elif data == STATE_STOPPED and error:
                _LOGGER.error(
                    "Websocket to %s failed, aborting [Error: %s]",
                    self.websocket.uri,
                    error,
                )
                self._ws_listening = False

        elif msgtype == "data":
            _LOGGER.debug("Websocket data: %s", data)
            keys = data.keys()
            if "wh" in keys:
                data["watthour"] = data.pop("wh")
            # TODO: update specific endpoints based on _version prefix
            if any(key in keys for key in UPDATE_TRIGGERS):
                await self.update()
            self._status.update(data)

            if self.callback is not None:
                self.callback()  # pylint: disable=not-callable

    async def ws_disconnect(self) -> None:
        """Disconnect the websocket listener."""
        assert self.websocket
        await self.websocket.close()
        self._ws_listening = False

    @property
    def ws_state(self) -> Any:
        """Return the status of the websocket listener."""
        assert self.websocket
        return self.websocket.state

    async def get_schedule(self) -> Union[Dict[str, str], Dict[str, Any]]:
        """Return the current schedule."""
        url = f"{self.url}schedule"

        _LOGGER.debug("Getting current schedule from %s", url)
        response = await self.process_request(url=url, method="post")
        return response

    async def set_charge_mode(self, mode: str = "fast") -> None:
        """Set the charge mode."""
        url = f"{self.url}config"

        if mode not in ["fast", "eco"]:
            _LOGGER.error("Invalid value for charge_mode: %s", mode)
            raise ValueError

        data = {"charge_mode": mode}

        _LOGGER.debug("Setting charge mode to %s", mode)
        response = await self.process_request(
            url=url, method="post", data=data
        )  # noqa: E501
        result = response["msg"]
        if result not in ["done", "no change"]:
            _LOGGER.error("Problem issuing command: %s", response["msg"])
            raise UnknownError

    async def divert_mode(self) -> dict[str, str] | dict[str, Any]:
        """Set the divert mode to either Normal or Eco modes."""
        if not self._version_check("4.0.0"):
            _LOGGER.debug("Feature not supported for older firmware.")
            raise UnsupportedFeature

        assert self._config

        if "divert_enabled" in self._config:
            _LOGGER.debug("Divert Enabled: %s", self._config["divert_enabled"])
            mode = not self._config["divert_enabled"]
        else:
            _LOGGER.debug("Unable to check divert status.")
            raise UnsupportedFeature

        url = f"{self.url}config"
        data = {"divert_enabled": mode}

        _LOGGER.debug("Toggling divert: %s", mode)
        response = await self.process_request(
            url=url, method="post", data=data
        )  # noqa: E501
        _LOGGER.debug("divert_mode response: %s", response)
        return response

    async def get_override(self) -> Union[Dict[str, str], Dict[str, Any]]:
        """Get the manual override status."""
        if not self._version_check("4.0.0"):
            _LOGGER.debug("Feature not supported for older firmware.")
            raise UnsupportedFeature
        url = f"{self.url}override"

        _LOGGER.debug("Getting data from %s", url)
        response = await self.process_request(url=url, method="get")
        return response

    async def set_override(
        self,
        state: str | None = None,
        charge_current: int | None = None,
        max_current: int | None = None,
        energy_limit: int | None = None,
        time_limit: int | None = None,
        auto_release: bool = True,
    ) -> Any:
        """Set the manual override status."""
        if not self._version_check("4.0.0"):
            _LOGGER.debug("Feature not supported for older firmware.")
            raise UnsupportedFeature
        url = f"{self.url}override"

        data: dict[str, Any] = {}

        if state not in ["active", "disabled", None]:
            _LOGGER.error("Invalid override state: %s", state)
            raise ValueError

        data["auto_release"] = auto_release

        if state is not None:
            data["state"] = state
        if charge_current is not None:
            data["charge_current"] = charge_current
        if max_current is not None:
            data["max_current"] = max_current
        if energy_limit is not None:
            data["energy_limit"] = energy_limit
        if time_limit is not None:
            data["time_limit"] = time_limit

        _LOGGER.debug("Override data: %s", data)
        _LOGGER.debug("Setting override config on %s", url)
        response = await self.process_request(
            url=url, method="post", data=data
        )  # noqa: E501
        return response

    async def toggle_override(self) -> None:
        """Toggle the manual override status."""
        #   3.x: use RAPI commands $FE (enable) and $FS (sleep)
        #   4.x: use HTTP API call
        lower = "4.0.0"
        if self._version_check(lower):
            url = f"{self.url}override"

            _LOGGER.debug("Toggling manual override %s", url)
            response = await self.process_request(url=url, method="patch")
            _LOGGER.debug("Toggle response: %s", response)
        else:
            # Older firmware use RAPI commands
            _LOGGER.debug("Toggling manual override via RAPI")
            command = "$FE" if self._status["state"] == 254 else "$FS"
            response, msg = await self.send_command(command)
            _LOGGER.debug("Toggle response: %s", msg)

    async def clear_override(self) -> None:
        """Clear the manual override status."""
        if not self._version_check("4.0.0"):
            _LOGGER.debug("Feature not supported for older firmware.")
            raise UnsupportedFeature
        url = f"{self.url}override"

        _LOGGER.debug("Clearing manual override %s", url)
        response = await self.process_request(url=url, method="delete")
        _LOGGER.debug("Toggle response: %s", response["msg"])

    async def set_current(self, amps: int = 6) -> None:
        """Set the soft current limit."""
        #   3.x - 4.1.0: use RAPI commands $SC <amps>
        #   4.1.2: use HTTP API call
        amps = int(amps)

        if self._version_check("4.1.2"):
            if (
                amps < self._config["min_current_hard"]
                or amps > self._config["max_current_hard"]
            ):
                _LOGGER.error("Invalid value for current limit: %s", amps)
                raise ValueError

            _LOGGER.debug("Setting current limit to %s", amps)
            response = await self.set_override(charge_current=amps)
            _LOGGER.debug("Set current response: %s", response)

        else:
            # RAPI commands
            _LOGGER.debug("Setting current via RAPI")
            command = f"$SC {amps} N"
            response, msg = await self.send_command(command)
            _LOGGER.debug("Set current response: %s", msg)

    async def set_service_level(self, level: int = 2) -> None:
        """Set the service level of the EVSE."""
        if not isinstance(level, int) or not 0 <= level <= 2:
            _LOGGER.error("Invalid service level: %s", level)
            raise ValueError

        url = f"{self.url}config"
        data = {"service": level}

        _LOGGER.debug("Set service level to: %s", level)
        response = await self.process_request(
            url=url, method="post", data=data
        )  # noqa: E501
        _LOGGER.debug("service response: %s", response)
        result = response["msg"]
        if result not in ["done", "no change"]:
            _LOGGER.error("Problem issuing command: %s", response["msg"])
            raise UnknownError

    # Restart OpenEVSE WiFi
    async def restart_wifi(self) -> None:
        """Restart OpenEVSE WiFi module."""
        url = f"{self.url}restart"

        response = await self.process_request(url=url, method="get")
        _LOGGER.debug("WiFi Restart response: %s", response)

    # Restart EVSE module
    async def restart_evse(self) -> None:
        """Restart EVSE module."""
        _LOGGER.debug("Restarting EVSE module via RAPI")
        command = "$FR"

        response = await self.send_command(command)
        if isinstance(response, tuple):
            response = response[1]
        _LOGGER.debug("EVSE Restart response: %s", response)

    # Firmwave version
    async def firmware_check(self) -> dict | None:
        """Return the latest firmware version."""
        if "version" not in self._config:
            # Throw warning if we can't find the version
            _LOGGER.warning("Unable to find firmware version.")
            return None
        base_url = "https://api.github.com/repos/OpenEVSE/"
        url = None
        method = "get"

        cutoff = AwesomeVersion("4.0.0")
        current = ""

        _LOGGER.debug("Detected firmware: %s", self._config["version"])

        if "dev" in self._config["version"]:
            value = self._config["version"]
            _LOGGER.debug("Stripping 'dev' from version.")
            value = value.split(".")
            value = ".".join(value[0:3])
            _LOGGER.debug("Using version: %s", value)
            current = AwesomeVersion(value)
        else:
            current = AwesomeVersion(self._config["version"])

        if current >= cutoff:
            url = f"{base_url}ESP32_WiFi_V4.x/releases/latest"
        else:
            url = f"{base_url}ESP8266_WiFi_v2.x/releases/latest"

        try:
            async with aiohttp.ClientSession() as session:
                http_method = getattr(session, method)
                _LOGGER.debug(
                    "Connecting to %s using method %s",
                    url,
                    method,
                )
                async with http_method(url) as resp:
                    if resp.status != 200:
                        return None
                    message = await resp.text()
                    message = json.loads(message)
                    response = {}
                    response["latest_version"] = message["tag_name"]
                    release_notes = message["body"]
                    response["release_summary"] = (
                        (release_notes[:253] + "..")
                        if len(release_notes) > 255
                        else release_notes
                    )
                    response["release_url"] = message["html_url"]
                    return response

        except (TimeoutError, ServerTimeoutError):
            _LOGGER.error("%s: %s", ERROR_TIMEOUT, url)
        except ContentTypeError as err:
            _LOGGER.error("%s", err)
        except aiohttp.ClientConnectorError as err:
            _LOGGER.error("%s : %s", err, url)

        return None

    def _version_check(self, min_version: str, max_version: str = "") -> bool:
        """Return bool if minimum version is met."""
        if "version" not in self._config:
            # Throw warning if we can't find the version
            _LOGGER.warning("Unable to find firmware version.")
            return False
        cutoff = AwesomeVersion(min_version)
        current = ""
        limit = ""
        if max_version != "":
            limit = AwesomeVersion(max_version)

        _LOGGER.debug("Detected firmware: %s", self._config["version"])

        if "dev" in self._config["version"]:
            value = self._config["version"]
            _LOGGER.debug("Stripping 'dev' from version.")
            value = value.split(".")
            value = ".".join(value[0:3])
            current = AwesomeVersion(value)
        else:
            current = AwesomeVersion(self._config["version"])

        if limit:
            if cutoff <= current <= limit:
                return True
            return False
        if current >= cutoff:
            return True
        return False

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
    def max_current_soft(self) -> int | None:
        """Return the firmware version."""
        if self._config is not None and "max_current_soft" in self._config:
            return self._config["max_current_soft"]
        return self._status["pilot"]

    @property
    def wifi_firmware(self) -> str:
        """Return the ESP firmware version."""
        assert self._config is not None
        value = self._config["version"]
        if "dev" in value:
            _LOGGER.debug("Stripping 'dev' from version.")
            value = value.split(".")
            value = ".".join(value[0:3])
        return value

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
    def state_raw(self) -> int:
        """Return charger's state int form."""
        assert self._status is not None
        return self._status["state"]

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
        if "total_energy" in self._status:
            return self._status["total_energy"]
        return self._status["watthour"]

    @property
    def ambient_temperature(self) -> float | None:
        """Return the temperature of the ambient sensor, in degrees Celsius."""
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

        In degrees Celsius.
        """
        assert self._status is not None
        temp = self._status["temp2"] if self._status["temp2"] else None
        if temp is not None:
            return temp / 10
        return None

    @property
    def ir_temperature(self) -> float | None:
        """Return the temperature of the IR remote sensor.

        In degrees Celsius.
        """
        assert self._status is not None
        temp = self._status["temp3"] if self._status["temp3"] else None
        if temp is not None:
            return temp / 10
        return None

    @property
    def esp_temperature(self) -> float | None:
        """Return the temperature of the ESP sensor, in degrees Celsius."""
        assert self._status is not None
        if "temp4" in self._status:
            temp = self._status["temp4"] if self._status["temp4"] else None
            if temp is not None:
                return temp / 10
        return None

    @property
    def time(self) -> datetime.datetime | None:
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
        if "session_energy" in self._status:
            return self._status["session_energy"]
        return float(round(self._status["wattsec"] / 3600, 2))

    @property
    def total_day(self) -> float | None:
        """Get the total day energy usage."""
        assert self._status is not None
        if "total_day" in self._status:
            return self._status["total_day"]
        return None

    @property
    def total_week(self) -> float | None:
        """Get the total week energy usage."""
        assert self._status is not None
        if "total_week" in self._status:
            return self._status["total_week"]
        return None

    @property
    def total_month(self) -> float | None:
        """Get the total week energy usage."""
        assert self._status is not None
        if "total_month" in self._status:
            return self._status["total_month"]
        return None

    @property
    def total_year(self) -> float | None:
        """Get the total year energy usage."""
        assert self._status is not None
        if "total_year" in self._status:
            return self._status["total_year"]
        return None

    @property
    def has_limit(self) -> bool | None:
        """Return if a limit has been set."""
        assert self._status is not None
        if "has_limit" in self._status:
            return self._status["has_limit"]
        return None

    @property
    def protocol_version(self) -> str | None:
        """Return the protocol version."""
        assert self._config is not None
        if self._config["protocol"] == "-":
            return None
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

    @property
    def manual_override(self) -> str:
        """Return if Manual Override is set."""
        assert self._status is not None
        return self._status["manual_override"]

    @property
    def divertmode(self) -> str:
        """Return the divert mode."""
        assert self._status is not None
        mode = self._status["divertmode"]
        if mode == 1:
            return "normal"
        return "eco"

    @property
    def charge_mode(self) -> str:
        """Return the charge mode."""
        assert self._config is not None
        return self._config["charge_mode"]

    @property
    def available_current(self) -> float:
        """Return the computed available current for divert."""
        assert self._status is not None
        return self._status["available_current"]

    @property
    def smoothed_available_current(self) -> float:
        """Return the computed smoothed available current for divert."""
        assert self._status is not None
        return self._status["smoothed_available_current"]

    @property
    def charge_rate(self) -> float:
        """Return the divert charge rate."""
        assert self._status is not None
        return self._status["charge_rate"]

    @property
    def divert_active(self) -> bool:
        """Return if divert is active."""
        assert self._config is not None
        if "divert_enabled" in self._config:
            return self._config["divert_enabled"]
        return False

    @property
    def wifi_serial(self) -> str | None:
        """Return wifi serial."""
        if self._config is not None and "wifi_serial" in self._config:
            return self._config["wifi_serial"]
        return None

    @property
    def charging_power(self) -> float | None:
        """Return the charge power.

        Calculate Watts base on V*I
        """
        if self._status is not None and any(
            key in self._status for key in ["voltage", "amp"]
        ):
            return round(self._status["voltage"] * self._status["amp"], 2)
        return None

    @property
    def shaper_active(self) -> bool | None:
        """Return if shper is active."""
        if self._status is not None and "shaper" in self._status:
            return bool(self._status["shaper"])
        return None

    @property
    def shaper_live_power(self) -> int | None:
        """Return shaper live power reading."""
        if self._status is not None and "shaper_live_pwr" in self._status:
            return self._status["shaper_live_pwr"]
        return None

    @property
    def shaper_current_power(self) -> int | None:
        """Return shaper live power reading."""
        if self._status is not None and "shaper_cur" in self._status:
            if self._status["shaper_cur"] == 255:
                return self._status["pilot"]
            return self._status["shaper_cur"]
        return None

    @property
    def shaper_max_power(self) -> int | None:
        """Return shaper live power reading."""
        if self._status is not None and "shaper_max_pwr" in self._status:
            return self._status["shaper_max_pwr"]
        return None

    @property
    def vehicle_soc(self) -> int | None:
        """Return battery level."""
        if self._status is not None and "vehicle_soc" in self._status:
            return self._status["vehicle_soc"]
        return None

    @property
    def vehicle_range(self) -> int | None:
        """Return battery range."""
        if self._status is not None and "vehicle_range" in self._status:
            return self._status["vehicle_range"]
        return None

    @property
    def vehicle_eta(self) -> int | None:
        """Return time to full charge."""
        if self._status is not None and "vehicle_eta" in self._status:
            return self._status["vehicle_eta"]
        return None

    # There is currently no min/max amps JSON data
    # available via HTTP API methods
    @property
    def min_amps(self) -> int:
        """Return the minimum amps."""
        if self._config is not None and "min_current_hard" in self._config:
            return self._config["min_current_hard"]
        return MIN_AMPS

    @property
    def max_amps(self) -> int:
        """Return the maximum amps."""
        if self._config is not None and "max_current_hard" in self._config:
            return self._config["max_current_hard"]
        return MAX_AMPS
