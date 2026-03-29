"""Main library functions for python-openevse-http."""

from __future__ import annotations

import asyncio
import datetime
import logging
from collections.abc import Callable
from typing import Any

import aiohttp

from .claims import Claims
from .const import (
    CLIENT,
    MAX_AMPS,
    MIN_AMPS,
)
from .exceptions import (
    AlreadyListening,
    MissingSerial,
    UnknownError,
    UnsupportedFeature,
)
from .firmware import Firmware
from .limit import Limit
from .override import Override
from .requester import Requester
from .sensors import Sensors
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

divert_mode_map = {
    "fast": 1,
    "eco": 2,
}

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

    def __init__(
        self,
        host: str,
        user: str = "",
        pwd: str = "",
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        """Connect to an OpenEVSE charger equipped with wifi or ethernet."""
        self._user = user
        self._pwd = pwd
        self.url = f"http://{host}/"
        self._status: dict = {}
        self._config: dict = {}
        self._ws_listening = False
        self.websocket: OpenEVSEWebsocket | None = None
        self.callback: Callable | None = None
        self._loop = None
        self.tasks = None
        self._session = session
        self._session_external = session is not None

        # Modules
        self.requester = Requester(host, user, pwd, session)
        self.requester.set_update_callback(self.update)
        self.firmware = Firmware(self)
        self.override = Override(self)
        self.limit = Limit(self)
        self.claims = Claims(self)
        self.sensors = Sensors(self)

    async def process_request(
        self,
        url: str,
        method: str = "get",
        data: Any = None,
        rapi: Any = None,
    ) -> dict[str, str] | dict[str, Any]:
        """Return result of processed HTTP request."""
        return await self.requester.process_request(
            url=url, method=method, data=data, rapi=rapi
        )

    async def send_command(self, command: str) -> tuple | dict:
        """Send a RAPI command to the charger and parses the response."""
        return await self.requester.send_command(command)

    async def update(self) -> None:
        """Update the values."""
        # TODO: add additional endpoints to update
        urls = [f"{self.url}config"]

        if not self._ws_listening:
            urls = [f"{self.url}status", f"{self.url}config"]

        for url in urls:
            _LOGGER.debug("Updating data from %s", url)
            response = await self.process_request(url, method="get")
            if isinstance(response, dict) and response.get("ok") is False:
                _LOGGER.debug("Update failed for %s, keeping previous cache.", url)
                continue

            if "/status" in url:
                self._status = response
                _LOGGER.debug("Status update: %s", self._status)

            else:
                self._config = response
                _LOGGER.debug("Config update: %s", self._config)

    def _extract_msg(self, response: Any) -> str | None:
        """Safely extract the 'msg' field from a response."""
        if isinstance(response, dict):
            return response.get("msg")
        if isinstance(response, str):
            return response
        return None

    async def test_and_get(self) -> dict:
        """Test connection.

        Return model serial number as dict
        """
        url = f"{self.url}config"

        response = await self.process_request(url, method="get")
        if not isinstance(response, dict) or response.get("ok") is False:
            _LOGGER.error("Problem getting config for serial detection: %s", response)
            raise UnknownError

        serial = response.get("wifi_serial")
        if serial is None:
            _LOGGER.debug(
                "Older firmware detected, missing serial. Response: %s", response
            )
            raise MissingSerial
        model = (
            response.get("buildenv", "unknown")
            if isinstance(response, dict)
            else "unknown"
        )

        data = {"serial": serial, "model": model}
        return data

    async def ws_start(self) -> None:
        """Start the websocket listener."""
        if self.websocket:
            if self._ws_listening and self.websocket.state == "connected":
                raise AlreadyListening
            if self._ws_listening and self.websocket.state != "connected":
                self._ws_listening = False
        await self._start_listening()

    async def _start_listening(self):
        """Websocket setup."""
        if not self.websocket:
            _LOGGER.debug("Websocket not initialized, creating...")
            self.websocket = OpenEVSEWebsocket(
                self.url, self._update_status, self._user, self._pwd, self._session
            )

        if not self._loop:
            try:
                _LOGGER.debug("Attempting to find running loop...")
                self._loop = asyncio.get_running_loop()
            except RuntimeError:
                self._loop = asyncio.get_event_loop()
                _LOGGER.debug("Using new event loop...")

        # Check for existing active tasks to avoid duplicates
        active_tasks = []
        if self.tasks:
            active_tasks = [t for t in self.tasks if not t.done()]

        if not self._ws_listening and not active_tasks:
            _LOGGER.debug("Setting up websocket ping...")
            self.tasks = [
                self._loop.create_task(self.websocket.listen()),
                self._loop.create_task(self.repeat(300, self.websocket.keepalive)),
            ]
            self._ws_listening = True
        elif active_tasks:
            _LOGGER.debug("Cleaning up orphaned websocket tasks before restart...")
            for task in active_tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*active_tasks, return_exceptions=True)
            self.tasks = [
                self._loop.create_task(self.websocket.listen()),
                self._loop.create_task(self.repeat(300, self.websocket.keepalive)),
            ]
            self._ws_listening = True

    async def _update_status(self, msgtype, data, error):
        """Update data from websocket listener."""
        if msgtype == SIGNAL_CONNECTION_STATE:
            uri = (
                getattr(self.websocket, "uri", "unknown") if self.websocket else "None"
            )
            if data == STATE_CONNECTED:
                _LOGGER.debug("Websocket to %s successful", uri)
                self._ws_listening = True
            elif data == STATE_DISCONNECTED:
                _LOGGER.debug(
                    "Websocket to %s disconnected, retrying",
                    uri,
                )
                _LOGGER.debug("Disconnect message: %s", error)
                self._ws_listening = False

            # Stopped websockets without errors are expected during shutdown
            # and ignored
            elif data == STATE_STOPPED and error:
                _LOGGER.debug(
                    "Websocket to %s failed, aborting [Error: %s]",
                    uri,
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
                try:
                    await self.update()
                except Exception as err:  # pylint: disable=broad-exception-caught
                    _LOGGER.error(
                        "Update failed during websocket push (triggers: %s): %s",
                        [k for k in keys if k in UPDATE_TRIGGERS],
                        err,
                    )
            self._status.update(data)

            if self.callback is not None:
                try:
                    if self.is_coroutine_function(self.callback):
                        await self.callback()  # pylint: disable=not-callable
                    else:
                        self.callback()  # pylint: disable=not-callable
                except Exception as err:  # pylint: disable=broad-exception-caught
                    _LOGGER.exception("Exception in user callback: %s", err)

    def set_update_callback(self, callback: Callable | None) -> None:
        """Set the update callback."""
        self.callback = callback

    async def ws_disconnect(self) -> None:
        """Disconnect the websocket listener (idempotent)."""
        if not self._ws_listening and not self.tasks and self.websocket is None:
            return

        self._ws_listening = False
        if self.tasks:
            for task in self.tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*self.tasks, return_exceptions=True)
            self.tasks = None

        if self.websocket is not None:
            await self.websocket.close()
            # We don't nullify self.websocket here as it may be reused by ws_start
            # unless the user expects it to be recreated.
            # But the requirement says 'set self.websocket to None so repeated calls are safe'
            # Let's keep it consistent.
            self.websocket = None

    def is_coroutine_function(self, callback):
        """Check if a callback is a coroutine function."""
        return asyncio.iscoroutinefunction(callback)

    @property
    def ws_state(self) -> Any:
        """Return the status of the websocket listener."""
        if self.websocket is None:
            return "stopped"
        return self.websocket.state

    async def repeat(self, interval, func, *args, **kwargs):
        """Run func every interval seconds.

        If func has not finished before *interval*, will run again
        immediately when the previous iteration finished.

        *args and **kwargs are passed as the arguments to func.
        """
        while self.ws_state != "stopped":
            await asyncio.sleep(interval)
            await func(*args, **kwargs)

    # Legacy method names for backward compatibility
    async def firmware_check(self) -> dict | None:
        """Proxy to firmware module."""
        return await self.firmware.check()

    def _version_check(self, min_version: str, max_version: str = "") -> bool:
        """Proxy to firmware module."""
        return self.firmware.version_check(min_version, max_version)

    def version_check(self, min_version: str, max_version: str = "") -> bool:
        """Proxy to firmware module."""
        return self.firmware.version_check(min_version, max_version)

    async def get_override(self) -> dict[str, str] | dict[str, Any]:
        """Proxy to override module."""
        return await self.override.get()

    async def set_override(
        self,
        state: str | None = None,
        charge_current: int | None = None,
        max_current: int | None = None,
        energy_limit: int | None = None,
        time_limit: int | None = None,
        auto_release: bool | None = None,
    ) -> Any:
        """Proxy to override module."""
        return await self.override.set(
            state=state,
            charge_current=charge_current,
            max_current=max_current,
            energy_limit=energy_limit,
            time_limit=time_limit,
            auto_release=auto_release,
        )

    async def toggle_override(self) -> None:
        """Proxy to override module."""
        await self.override.toggle()

    async def clear_override(self) -> None:
        """Proxy to override module."""
        await self.override.clear()

    async def set_limit(
        self, limit_type: str, value: int, release: bool | None = None
    ) -> Any:
        """Proxy to limit module."""
        return await self.limit.set(limit_type=limit_type, value=value, release=release)

    async def get_limit(self) -> Any:
        """Proxy to limit module."""
        return await self.limit.get()

    async def clear_limit(self) -> Any:
        """Proxy to limit module."""
        return await self.limit.clear()

    async def make_claim(
        self,
        state: str | None = None,
        charge_current: int | None = None,
        max_current: int | None = None,
        auto_release: bool = True,
        client: int = CLIENT,
    ) -> Any:
        """Proxy to claims module."""
        return await self.claims.make(
            state=state,
            charge_current=charge_current,
            max_current=max_current,
            auto_release=auto_release,
            client=client,
        )

    async def release_claim(self, client: int = CLIENT) -> Any:
        """Proxy to claims module."""
        return await self.claims.release(client=client)

    async def list_claims(self, target: bool | None = None) -> Any:
        """Proxy to claims module."""
        return await self.claims.list(target=target)

    async def grid_voltage(self, voltage: int | None = None) -> None:
        """Proxy to sensors module."""
        await self.sensors.grid_voltage(voltage=voltage)

    async def self_production(
        self,
        grid: int | None = None,
        solar: int | None = None,
        invert: bool = True,
        voltage: int | None = None,
    ) -> None:
        """Proxy to sensors module."""
        await self.sensors.self_production(
            grid=grid, solar=solar, invert=invert, voltage=voltage
        )

    async def soc(
        self,
        battery_level: int | None = None,
        battery_range: int | None = None,
        time_to_full: int | None = None,
        voltage: int | None = None,
    ) -> None:
        """Proxy to sensors module."""
        await self.sensors.soc(
            battery_level=battery_level,
            battery_range=battery_range,
            time_to_full=time_to_full,
            voltage=voltage,
        )

    async def set_shaper_live_pwr(self, power: int) -> None:
        """Proxy to sensors module."""
        await self.sensors.set_shaper_live_pwr(power=power)

    # Core Logic remains here or moved if appropriate
    async def get_schedule(self) -> dict[str, str] | dict[str, Any]:
        """Return the current schedule."""
        url = f"{self.url}schedule"

        _LOGGER.debug("Getting current schedule from %s", url)
        response = await self.process_request(url=url, method="post")
        return response

    async def set_charge_mode(self, mode: str = "fast") -> None:
        """Set the charge mode at startup setting."""
        url = f"{self.url}config"

        if mode not in ["fast", "eco"]:
            _LOGGER.error("Invalid value for charge_mode: %s", mode)
            raise ValueError

        data = {"charge_mode": mode}

        _LOGGER.debug("Setting charge mode to %s", mode)
        response = await self.process_request(url=url, method="post", data=data)
        result = self._extract_msg(response)
        if result not in ["done", "no change"]:
            _LOGGER.error("Problem issuing command. Response: %s", response)
            raise UnknownError

    async def divert_mode(self) -> dict[str, str] | dict[str, Any]:
        """Set the divert mode to either Normal or Eco modes."""
        if self._config is None:  # In case it is somehow set to None
            _LOGGER.debug("Configuration is missing.")
            raise UnsupportedFeature

        if not self._version_check("2.9.1"):
            _LOGGER.debug("Feature not supported for older firmware.")
            raise UnsupportedFeature

        if "divert_enabled" in self._config:
            _LOGGER.debug("Divert Enabled: %s", self._config["divert_enabled"])
            mode = not self._config["divert_enabled"]
        else:
            _LOGGER.debug("Unable to check divert status.")
            raise UnsupportedFeature

        url = f"{self.url}config"
        data = {"divert_enabled": mode}

        _LOGGER.debug("Toggling divert: %s", mode)
        response = await self.process_request(url=url, method="post", data=data)
        _LOGGER.debug("divert_mode response: %s", response)
        if not response.get("ok", False):
            _LOGGER.error("Problem toggling divert: %s", response)
            raise UnknownError

        # Update local cache on success
        self._config["divert_enabled"] = mode
        return response

    async def set_current(self, amps: int = 6) -> Any:
        """Set the soft current limit."""
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
            # Different parameters for older firmware
            if self._version_check("2.9.1"):
                command = f"$SC {amps} V"
            results = await self.send_command(command)
            if isinstance(results, dict):
                _LOGGER.error("Problem setting current limit. Response: %s", results)
                return False

            cmd, msg = results
            if cmd is False:
                _LOGGER.error("Problem setting current limit. Trace: %s", msg)
                return False

            if (isinstance(cmd, str) and cmd.startswith("$NK")) or (
                isinstance(msg, str) and (msg.startswith("$NK") or msg == "")
            ):
                _LOGGER.error(
                    "Problem setting current limit. Command: %s, Response: %s", cmd, msg
                )
                return False
            _LOGGER.debug("Set current response: %s", msg)
            return True

    async def set_service_level(self, level: int = 2) -> None:
        """Set the service level of the EVSE."""
        if not isinstance(level, int) or not 0 <= level <= 2:
            _LOGGER.error("Invalid service level: %s", level)
            raise ValueError

        url = f"{self.url}config"
        data = {"service": level}

        _LOGGER.debug("Set service level to: %s", level)
        response = await self.process_request(url=url, method="post", data=data)
        _LOGGER.debug("service response: %s", response)
        result = self._extract_msg(response)
        if result not in ["done", "no change"]:
            _LOGGER.error("Problem issuing command. Response: %s", response)
            raise UnknownError

    async def restart_wifi(self) -> None:
        """Restart OpenEVSE WiFi module."""
        url = f"{self.url}restart"
        data = {"device": "gateway"}

        response = await self.process_request(url=url, method="post", data=data)
        result = self._extract_msg(response)
        _LOGGER.debug("WiFi Restart response: %s", result)
        if result not in ["done", "no change", "restart gateway"]:
            _LOGGER.error("Problem issuing command. Response: %s", response)
            raise UnknownError

    async def restart_evse(self) -> None:
        """Restart EVSE module."""
        if self._version_check("5.0.0"):
            _LOGGER.debug("Restarting EVSE module via HTTP")
            url = f"{self.url}restart"
            data = {"device": "evse"}
            reply = await self.process_request(url=url, method="post", data=data)
            response = self._extract_msg(reply)

        else:
            _LOGGER.debug("Restarting EVSE module via RAPI")
            command = "$FR"
            results = await self.send_command(command)
            if isinstance(results, dict):
                _LOGGER.error("Problem restarting EVSE. Response: %s", results)
                response = ""
            else:
                _, response = results

        _LOGGER.debug("EVSE Restart response: %s", response)
        if response not in ["done", "no change", "OK", "restart evse"] and not str(
            response
        ).startswith("$OK"):
            _LOGGER.error("Problem issuing command. Response: %s", response)
            raise UnknownError

    async def set_led_brightness(self, level: int) -> None:
        """Set LED brightness level."""
        if not self._version_check("4.1.0"):
            _LOGGER.debug("Feature not supported for older firmware.")
            raise UnsupportedFeature

        url = f"{self.url}config"
        data: dict[str, Any] = {}

        data["led_brightness"] = level
        _LOGGER.debug("Setting LED brightness to %s", level)
        response = await self.process_request(url=url, method="post", data=data)
        _LOGGER.debug("led_brightness response: %s", response)
        result = self._extract_msg(response)
        if result not in ["done", "no change"]:
            _LOGGER.error("Problem issuing command. Response: %s", response)
            raise UnknownError

    async def set_divert_mode(self, mode: str = "fast") -> None:
        """Set the divert mode."""
        url = f"{self.url}divertmode"
        if mode not in ["fast", "eco"]:
            _LOGGER.error("Invalid value for divert mode: %s", mode)
            raise ValueError
        _LOGGER.debug("Setting divert mode to %s", mode)
        # convert text to int
        new_mode = divert_mode_map[mode]

        data = f"divertmode={new_mode}"

        response = await self.process_request(url=url, method="post", rapi=data)
        result = self._extract_msg(response)
        if result != "Divert Mode changed":
            _LOGGER.error("Problem issuing command. Response: %s", response)
            raise UnknownError

    # Properties
    @property
    def led_brightness(self) -> int | None:
        """Return charger led_brightness."""
        if not self._version_check("4.1.0"):
            _LOGGER.debug("Feature not supported for older firmware.")
            raise UnsupportedFeature
        return self._config.get("led_brightness")

    @property
    def hostname(self) -> str | None:
        """Return charger hostname."""
        return self._config.get("hostname")

    @property
    def wifi_ssid(self) -> str | None:
        """Return charger connected SSID."""
        return self._config.get("ssid")

    @property
    def ammeter_offset(self) -> int | None:
        """Return ammeter's current offset."""
        return self._config.get("offset")

    @property
    def ammeter_scale_factor(self) -> int | None:
        """Return ammeter's current scale factor."""
        return self._config.get("scale")

    @property
    def temp_check_enabled(self) -> bool:
        """Return True if enabled, False if disabled."""
        return bool(self._config.get("tempt", False))

    @property
    def diode_check_enabled(self) -> bool:
        """Return True if enabled, False if disabled."""
        return bool(self._config.get("diodet", False))

    @property
    def vent_required_enabled(self) -> bool:
        """Return True if enabled, False if disabled."""
        return bool(self._config.get("ventt", False))

    @property
    def ground_check_enabled(self) -> bool:
        """Return True if enabled, False if disabled."""
        return bool(self._config.get("groundt", False))

    @property
    def stuck_relay_check_enabled(self) -> bool:
        """Return True if enabled, False if disabled."""
        return bool(self._config.get("relayt", False))

    @property
    def service_level(self) -> str | None:
        """Return the service level."""
        return self._config.get("service")

    @property
    def openevse_firmware(self) -> str | None:
        """Return the firmware version."""
        return self._config.get("firmware")

    @property
    def max_current_soft(self) -> int | None:
        """Return the max current soft."""
        if "max_current_soft" in self._config:
            return self._config.get("max_current_soft")
        return self._status.get("pilot")

    async def get_charge_current(self) -> int | None:
        """Return the charge current."""
        try:
            claims = None
            claims = await self.list_claims(target=True)
        except UnsupportedFeature:
            pass
        if claims is not None and "charge_current" in claims["properties"].keys():
            return min(
                claims["properties"]["charge_current"], self._config["max_current_hard"]
            )
        if "max_current_soft" in self._config:
            return self._config.get("max_current_soft")
        return self._status.get("pilot")

    @property
    def max_current(self) -> int | None:
        """Return the max current."""
        return self._status.get("max_current", None)

    @property
    def wifi_firmware(self) -> str | None:
        """Return the ESP firmware version."""
        value = self._config.get("version")
        if value is not None and "dev" in value:
            _LOGGER.debug("Stripping 'dev' from version.")
            value = value.split(".")
            value = ".".join(value[0:3])
        return value

    @property
    def ip_address(self) -> str | None:
        """Return the ip address."""
        return self._status.get("ipaddress")

    @property
    def charging_voltage(self) -> int | None:
        """Return the charging voltage."""
        return self._status.get("voltage")

    @property
    def mode(self) -> str | None:
        """Return the mode."""
        return self._status.get("mode")

    @property
    def using_ethernet(self) -> bool:
        """Return True if enabled, False if disabled."""
        return bool(self._status.get("eth_connected", False))

    @property
    def stuck_relay_trip_count(self) -> int | None:
        """Return the stuck relay count."""
        return self._status.get("stuckcount")

    @property
    def no_gnd_trip_count(self) -> int | None:
        """Return the no ground count."""
        return self._status.get("nogndcount")

    @property
    def gfi_trip_count(self) -> int | None:
        """Return the GFCI count."""
        return self._status.get("gfcicount")

    @property
    def status(self) -> str:
        """Return charger's state."""
        if "status" in self._status:
            return self._status["status"]
        return self.state

    @property
    def state(self) -> str:
        """Return charger's state."""
        state_idx = self._status.get("state", 0)
        try:
            state_idx = int(state_idx)
        except (ValueError, TypeError):
            _LOGGER.debug("Invalid state value: %s", state_idx)
            return "unknown"
        return states.get(state_idx, "unknown")

    @property
    def state_raw(self) -> int | None:
        """Return charger's state int form."""
        return self._status.get("state")

    @property
    def charge_time_elapsed(self) -> int | None:
        """Return elapsed charging time."""
        return self._status.get("elapsed")

    @property
    def wifi_signal(self) -> str | None:
        """Return charger's wifi signal."""
        return self._status.get("srssi")

    @property
    def charging_current(self) -> float | None:
        """Return the charge current.

        0 if is not currently charging.
        """
        return self._status.get("amp")

    @property
    def current_capacity(self) -> int | None:
        """Return the current capacity."""
        return self._status.get("pilot")

    @property
    def usage_total(self) -> float | None:
        """Return the total energy usage in Wh."""
        if "total_energy" in self._status:
            return self._status.get("total_energy")
        return self._status.get("watthour")

    @property
    def ambient_temperature(self) -> float | None:
        """Return the temperature of the ambient sensor, in degrees Celsius."""
        temp = self._status.get("temp")
        if temp is not None:
            return temp / 10
        return self._status.get("temp1", 0) / 10

    @property
    def rtc_temperature(self) -> float | None:
        """Return the temperature of the real time clock sensor."""
        temp = self._status.get("temp2")
        if temp is None or isinstance(temp, bool):
            return None
        return float(temp) / 10

    @property
    def ir_temperature(self) -> float | None:
        """Return the temperature of the IR remote sensor.

        In degrees Celsius.
        """
        temp = self._status.get("temp3")
        if temp is None or isinstance(temp, bool):
            return None
        return float(temp) / 10

    @property
    def esp_temperature(self) -> float | None:
        """Return the temperature of the ESP sensor, in degrees Celsius."""
        temp = self._status.get("temp4")
        if temp is None or isinstance(temp, bool):
            return None
        return float(temp) / 10

    @property
    def time(self) -> datetime.datetime | None:
        """Get the RTC time."""
        value = self._status.get("time")
        if value:
            try:
                return datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                return None
        return None

    @property
    def usage_session(self) -> float | None:
        """Get the energy usage for the current charging session.

        Return the energy usage in Wh.
        """
        if "session_energy" in self._status:
            return self._status.get("session_energy")
        wattsec = self._status.get("wattsec")
        if wattsec is not None:
            return float(round(wattsec / 3600, 2))
        return None

    @property
    def total_day(self) -> float | None:
        """Get the total day energy usage."""
        return self._status.get("total_day", None)

    @property
    def total_week(self) -> float | None:
        """Get the total week energy usage."""
        return self._status.get("total_week", None)

    @property
    def total_month(self) -> float | None:
        """Get the total week energy usage."""
        return self._status.get("total_month", None)

    @property
    def total_year(self) -> float | None:
        """Get the total year energy usage."""
        return self._status.get("total_year", None)

    @property
    def has_limit(self) -> bool | None:
        """Return if a limit has been set."""
        return self._status.get("has_limit", self._status.get("limit", None))

    @property
    def protocol_version(self) -> str | None:
        """Return the protocol version."""
        protocol = self._config.get("protocol")
        if protocol == "-":
            return None
        return protocol

    @property
    def vehicle(self) -> bool:
        """Return if a vehicle is connected dto the EVSE."""
        return self._status.get("vehicle", False)

    @property
    def ota_update(self) -> bool:
        """Return if an OTA update is active."""
        return self._status.get("ota_update", False)

    @property
    def manual_override(self) -> bool:
        """Return if Manual Override is set."""
        return self._status.get("manual_override", False)

    @property
    def divertmode(self) -> str:
        """Return the divert mode."""
        mode = self._status.get("divertmode", 1)
        if mode == 1:
            return "fast"
        return "eco"

    @property
    def charge_mode(self) -> str | None:
        """Return the charge mode."""
        return self._config.get("charge_mode")

    @property
    def available_current(self) -> float | None:
        """Return the computed available current for divert."""
        return self._status.get("available_current")

    @property
    def smoothed_available_current(self) -> float | None:
        """Return the computed smoothed available current for divert."""
        return self._status.get("smoothed_available_current")

    @property
    def charge_rate(self) -> float | None:
        """Return the divert charge rate."""
        return self._status.get("charge_rate")

    @property
    def divert_active(self) -> bool:
        """Return if divert is active."""
        return bool(self._config.get("divert_enabled", False))

    @property
    def wifi_serial(self) -> str | None:
        """Return wifi serial."""
        return self._config.get("wifi_serial", None)

    @property
    def charging_power(self) -> float | None:
        """Return the charge power.

        Calculate Watts base on V*I
        """
        if self._status is not None and all(
            key in self._status for key in ["voltage", "amp"]
        ):
            return round(self._status["voltage"] * self._status["amp"], 2)
        return None

    @property
    def shaper_active(self) -> bool | None:
        """Return if shper is active."""
        return self._status.get("shaper", None)

    @property
    def shaper_live_power(self) -> int | None:
        """Return shaper live power reading."""
        return self._status.get("shaper_live_pwr", None)

    @property
    def shaper_available_current(self) -> float | None:
        """Return shaper available current."""
        shaper_cur = self._status.get("shaper_cur")
        if shaper_cur == 255:
            return self._status.get("pilot")
        return shaper_cur

    @property
    def shaper_max_power(self) -> int | None:
        """Return shaper live power reading."""
        return self._status.get("shaper_max_pwr", None)

    @property
    def shaper_updated(self) -> bool:
        """Return shaper updated boolean."""
        return bool(self._status.get("shaper_updated", False))

    @property
    def vehicle_soc(self) -> int | None:
        """Return battery level."""
        return self._status.get("vehicle_soc", self._status.get("battery_level", None))

    @property
    def vehicle_range(self) -> int | None:
        """Return battery range."""
        return self._status.get(
            "vehicle_range", self._status.get("battery_range", None)
        )

    @property
    def vehicle_eta(self) -> datetime.datetime | None:
        """Return time to full charge."""
        value = self._status.get(
            "time_to_full_charge", self._status.get("vehicle_eta", None)
        )
        if value is not None:
            return datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
                seconds=value
            )
        return value

    @property
    def min_amps(self) -> int:
        """Return the minimum amps."""
        return self._config.get("min_current_hard", MIN_AMPS)

    @property
    def max_amps(self) -> int:
        """Return the maximum amps."""
        return self._config.get("max_current_hard", MAX_AMPS)

    @property
    def mqtt_connected(self) -> bool:
        """Return the status of the mqtt connection."""
        return bool(self._status.get("mqtt_connected", False))

    @property
    def emoncms_connected(self) -> bool | None:
        """Return the status of the emoncms connection."""
        return self._status.get("emoncms_connected", None)

    @property
    def ocpp_connected(self) -> bool | None:
        """Return the status of the ocpp connection."""
        return self._status.get("ocpp_connected", None)

    @property
    def uptime(self) -> int | None:
        """Return the unit uptime."""
        return self._status.get("uptime", None)

    @property
    def freeram(self) -> int | None:
        """Return the unit freeram."""
        return self._status.get("freeram", None)

    @property
    def checks_count(self) -> dict:
        """Return the safety checks counts."""
        attributes = ("gfcicount", "nogndcount", "stuckcount")
        counts = {}
        if self._status is not None and set(attributes).issubset(self._status.keys()):
            counts["gfcicount"] = self._status["gfcicount"]
            counts["nogndcount"] = self._status["nogndcount"]
            counts["stuckcount"] = self._status["stuckcount"]
        return counts

    async def get_override_state(self) -> str | None:
        """Return the unit override state."""
        try:
            override = await self.get_override()
        except UnsupportedFeature:
            _LOGGER.debug("Override state unavailable on older firmware.")
            return None
        if not override.get("ok", True):
            _LOGGER.error("Problem getting status for override state: %s", override)
            return None

        if "state" in override:
            return override["state"]
        return "auto"

    @property
    def current_power(self) -> int:
        """Return the current power (live) in watts."""
        if not self._version_check("4.2.2"):
            _LOGGER.debug("Feature not supported for older firmware.")
            raise UnsupportedFeature
        return self._status.get("power", 0)
