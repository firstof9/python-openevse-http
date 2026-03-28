"""Firmware check class for OpenEVSE HTTP."""

from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING

import aiohttp
from aiohttp.client_exceptions import ContentTypeError, ServerTimeoutError
from awesomeversion import AwesomeVersion
from awesomeversion.exceptions import AwesomeVersionCompareException

if TYPE_CHECKING:
    from .client import OpenEVSE

_LOGGER = logging.getLogger(__name__)

ERROR_TIMEOUT = "Timeout while updating"


class Firmware:
    """Handle firmware checks for OpenEVSE."""

    def __init__(self, evse: OpenEVSE) -> None:
        """Initialize the firmware class."""
        self._evse = evse

    async def check(self) -> dict | None:
        """Return the latest firmware version."""
        if "version" not in self._evse._config:
            # Throw warning if we can't find the version
            _LOGGER.warning("Unable to find firmware version.")
            return None
        base_url = "https://api.github.com/repos/OpenEVSE/"
        url = None
        method = "get"

        cutoff = AwesomeVersion("3.0.0")

        _LOGGER.debug("Detected firmware: %s", self._evse._config["version"])

        if "dev" in self._evse._config["version"]:
            value = self._evse._config["version"]
            _LOGGER.debug("Stripping 'dev' from version.")
            value = value.split(".")
            value = ".".join(value[0:3])
        elif "master" in self._evse._config["version"]:
            value = "dev"
        else:
            value = self._evse._config["version"]

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
            if (session := self._evse._session) is None:
                async with aiohttp.ClientSession() as session:
                    return await self._firmware_check_with_session(session, url, method)
            else:
                return await self._firmware_check_with_session(session, url, method)

        except (TimeoutError, ServerTimeoutError):
            _LOGGER.error("%s: %s", ERROR_TIMEOUT, url)
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

            response = {}
            if isinstance(message, dict):
                response["latest_version"] = message.get("tag_name")
                response["release_notes"] = message.get("body")
                response["release_url"] = message.get("html_url")
            return response

    def version_check(self, min_version: str, max_version: str = "") -> bool:
        """Return bool if minimum version is met."""
        if "version" not in self._evse._config:
            # Throw warning if we can't find the version
            _LOGGER.warning("Unable to find firmware version.")
            return False
        cutoff = AwesomeVersion(min_version)
        current = ""
        limit = ""
        if max_version != "":
            limit = AwesomeVersion(max_version)

        firmware_filtered = None

        try:
            firmware_search = re.search(
                "\\d\\.\\d\\.\\d", self._evse._config["version"]
            )
            if firmware_search is not None:
                firmware_filtered = firmware_search[0]
        except Exception:  # pylint: disable=broad-exception-caught
            _LOGGER.warning("Non-standard versioning string.")
        _LOGGER.debug("Detected firmware: %s", self._evse._config["version"])
        _LOGGER.debug("Filtered firmware: %s", firmware_filtered)

        if "dev" in self._evse._config["version"]:
            value = self._evse._config["version"]
            _LOGGER.debug("Stripping 'dev' from version.")
            value = value.split(".")
            value = ".".join(value[0:3])
        elif "master" in self._evse._config["version"]:
            value = "dev"
        else:
            value = firmware_filtered

        current = AwesomeVersion(value)

        if limit:
            try:
                if cutoff <= current <= limit:
                    return True
            except AwesomeVersionCompareException:
                _LOGGER.debug("Non-semver firmware version detected.")
            return False

        try:
            if current >= cutoff:
                return True
        except AwesomeVersionCompareException:
            _LOGGER.debug("Non-semver firmware version detected.")
        return False
