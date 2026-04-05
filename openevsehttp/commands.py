"""Command methods for the OpenEVSE charger."""

from __future__ import annotations

import json
import logging
from typing import Any

import aiohttp  # type: ignore
from aiohttp.client_exceptions import ContentTypeError, ServerTimeoutError
from awesomeversion import AwesomeVersion
from awesomeversion.exceptions import AwesomeVersionCompareException

from .const import MAX_AMPS, MIN_AMPS, divert_mode
from .exceptions import UnknownError, UnsupportedFeature

_LOGGER = logging.getLogger(__name__)


class CommandsMixin:
    """Mixin providing command methods for OpenEVSE."""

    url: str
    _status: dict
    _config: dict
    _session: Any

    # These are defined in client.py
    def _version_check(self, min_version: str, max_version: str = "") -> bool:
        raise NotImplementedError

    async def process_request(
        self, url: str, method: str = "", data: Any = None, rapi: Any = None
    ) -> dict[str, str] | dict[str, Any]:
        raise NotImplementedError

    async def send_command(self, command: str) -> tuple:
        raise NotImplementedError

    async def update(self) -> None:
        raise NotImplementedError

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
        msg = response.get("msg")
        if msg not in ["done", "no change"]:
            _LOGGER.error("Problem issuing command: %s", response)
            raise UnknownError

    async def divert_mode(self) -> dict[str, str] | dict[str, Any]:
        """Set the divert mode to either Normal or Eco modes."""
        if not self._config:
            raise RuntimeError("Missing configuration: self._config is required")

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
        if isinstance(response, dict) and response.get("msg") in [
            "OK",
            "done",
            "no change",
        ]:
            self._config["divert_enabled"] = mode
        return response

    async def get_override(self) -> dict[str, str] | dict[str, Any]:
        """Get the manual override status."""
        if not self._version_check("4.0.1"):
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
        if not self._version_check("4.0.1"):
            _LOGGER.debug("Feature not supported for older firmware.")
            raise UnsupportedFeature
        url = f"{self.url}override"

        data: dict[str, Any] = await self.get_override()

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
        response = await self.process_request(url=url, method="post", data=data)
        return response

    async def toggle_override(self) -> None:
        """Toggle the manual override status."""
        #   3.x: use RAPI commands $FE (enable) and $FS (sleep)
        #   4.x: use HTTP API call
        lower = "4.0.1"
        msg = ""
        if self._version_check(lower):
            url = f"{self.url}override"

            _LOGGER.debug("Toggling manual override %s", url)
            response = await self.process_request(url=url, method="patch")
            _LOGGER.debug("Toggle response: %s", response)
        else:
            # Older firmware use RAPI commands
            _LOGGER.debug("Toggling manual override via RAPI")
            command = "$FE" if self._status.get("state", 0) == 254 else "$FS"
            response, msg = await self.send_command(command)
            _LOGGER.debug("Toggle response: %s", msg)

    async def clear_override(self) -> None:
        """Clear the manual override status."""
        if not self._version_check("4.0.1"):
            _LOGGER.debug("Feature not supported for older firmware.")
            raise UnsupportedFeature
        url = f"{self.url}override"

        _LOGGER.debug("Clearing manual override %s", url)
        response = await self.process_request(url=url, method="delete")
        _LOGGER.debug("Toggle response: %s", response.get("msg", response))

    async def set_current(self, amps: int = 6) -> None:
        """Set the soft current limit."""
        #   3.x - 4.1.0: use RAPI commands $SC <amps>
        #   4.1.2: use HTTP API call
        amps = int(amps)
        min_current = self._config.get("min_current_hard", MIN_AMPS)
        max_current = self._config.get("max_current_hard", MAX_AMPS)
        if amps < min_current or amps > max_current:
            _LOGGER.error("Invalid value for current limit: %s", amps)
            raise ValueError

        if self._version_check("4.1.2"):
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
        response = await self.process_request(url=url, method="post", data=data)
        _LOGGER.debug("service response: %s", response)
        msg = response.get("msg")
        if msg not in ["done", "no change"]:
            _LOGGER.error("Problem issuing command: %s", response)
            raise UnknownError

    # Restart OpenEVSE WiFi
    async def restart_wifi(self) -> None:
        """Restart OpenEVSE WiFi module."""
        url = f"{self.url}restart"
        data = {"device": "gateway"}

        response = await self.process_request(url=url, method="post", data=data)
        _LOGGER.debug("WiFi Restart response: %s", response.get("msg", response))

    # Restart EVSE module
    async def restart_evse(self) -> None:
        """Restart EVSE module."""
        if self._version_check("5.0.0"):
            _LOGGER.debug("Restarting EVSE module via HTTP")
            url = f"{self.url}restart"
            data = {"device": "evse"}
            reply = await self.process_request(url=url, method="post", data=data)
            response = reply.get("msg", "Unknown error")

        else:
            _LOGGER.debug("Restarting EVSE module via RAPI")
            command = "$FR"
            reply, response = await self.send_command(command)

        _LOGGER.debug("EVSE Restart response: %s", response)

    # Firmware version
    async def firmware_check(self) -> dict | None:
        """Return the latest firmware version."""
        if "version" not in self._config:
            # Throw warning if we can't find the version
            _LOGGER.warning("Unable to find firmware version.")
            return None
        base_url = "https://api.github.com/repos/OpenEVSE/"
        url = None
        method = "get"

        cutoff = AwesomeVersion("3.0.0")
        current = ""

        _LOGGER.debug("Detected firmware: %s", self._config["version"])

        if "dev" in self._config["version"]:
            value = self._config["version"]
            _LOGGER.debug("Stripping 'dev' from version.")
            value = value.split(".")
            value = ".".join(value[0:3])
        elif "master" in self._config["version"]:
            value = "dev"
        else:
            value = self._config["version"]

        _LOGGER.debug("Using version: %s", value)
        current = AwesomeVersion(value)

        try:
            if current >= cutoff:
                url = f"{base_url}ESP32_WiFi_V4.x/releases/latest"
            else:
                url = f"{base_url}ESP8266_WiFi_v2.x/releases/latest"
        except AwesomeVersionCompareException:
            _LOGGER.warning("Non-semver firmware version detected.")
            return None

        try:
            if (session := self._session) is None:
                async with aiohttp.ClientSession() as session:
                    return await self._firmware_check_with_session(session, url, method)
            else:
                return await self._firmware_check_with_session(session, url, method)

        except (TimeoutError, ServerTimeoutError):
            _LOGGER.error("%s: %s", "Timeout while updating", url)
        except ContentTypeError as err:
            _LOGGER.error("%s", err)
        except aiohttp.ClientConnectorError as err:
            _LOGGER.error("%s : %s", err, url)

        return None

    async def _firmware_check_with_session(
        self, session: aiohttp.ClientSession, url: str, method: str
    ) -> dict | None:
        """Process a firmware check request with a given session."""
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
            try:
                message = json.loads(message)
            except json.JSONDecodeError:
                _LOGGER.error("Failed to parse JSON response: %s", message)
                return None

            if not isinstance(message, dict):
                return None
            return {
                "latest_version": message.get("tag_name"),
                "release_notes": message.get("body"),
                "release_url": message.get("html_url"),
            }

    async def set_led_brightness(self, level: int) -> None:
        """Set LED brightness level."""
        if not self._version_check("4.1.0"):
            _LOGGER.debug("Feature not supported for older firmware.")
            raise UnsupportedFeature

        url = f"{self.url}config"
        data: dict[str, Any] = {}

        data["led_brightness"] = level
        _LOGGER.debug("Setting LED brightness to %s", level)
        await self.process_request(url=url, method="post", data=data)

    async def set_divert_mode(self, mode: str = "fast") -> None:
        """Set the divert mode."""
        url = f"{self.url}divertmode"
        if mode not in ["fast", "eco"]:
            _LOGGER.error("Invalid value for divert mode: %s", mode)
            raise ValueError
        _LOGGER.debug("Setting divert mode to %s", mode)
        # convert text to int
        new_mode = divert_mode[mode]

        data = f"divertmode={new_mode}"

        response = await self.process_request(url=url, method="post", rapi=data)
        success = False
        if isinstance(response, str):
            res_lower = response.lower()
            if "divert" in res_lower and "changed" in res_lower:
                success = True
        elif isinstance(response, dict) and response.get("msg") in [
            "OK",
            "done",
            "no change",
        ]:
            success = True

        if not success:
            _LOGGER.error("Problem issuing command: %s", response)
            raise UnknownError
