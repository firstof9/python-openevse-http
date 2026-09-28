"""Firmware check and update command methods for the OpenEVSE charger."""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from typing import Any

import aiohttp
from aiohttp.client_exceptions import ContentTypeError, ServerTimeoutError
from awesomeversion import AwesomeVersion
from awesomeversion.exceptions import AwesomeVersionCompareException

from .commands_base import BaseCommandMixin
from .const import SUCCESS_ANSWERS
from .exceptions import (
    FirmwareResolutionError,
    UnsupportedFeature,
)
from .utils import get_awesome_version

_LOGGER = logging.getLogger(__name__)


class FirmwareCommandsMixin(BaseCommandMixin):
    """Mixin providing firmware checking and OTA update commands."""

    def _flag_ota_if_started(self, response: Any) -> None:
        """Flag OTA as active if response indicates firmware update has started."""
        normalized = self._normalize_response(response)
        if isinstance(normalized, dict) and (
            normalized.get("msg") == "started"
            or normalized.get("msg") in SUCCESS_ANSWERS
        ):
            _LOGGER.debug("Firmware update started, setting ota_update flag.")
            self._status["ota_update"] = 1
        else:
            _LOGGER.debug(
                "Firmware update response did not indicate start: %s", normalized
            )

    async def firmware_check(self) -> dict[str, Any] | None:
        """Return the latest firmware version."""
        if "version" not in self._config:
            # Throw warning if we can't find the version
            _LOGGER.debug("Unable to find firmware version.")
            return None
        base_url = "https://api.github.com/repos/OpenEVSE/"
        url = None
        method = "get"

        cutoff = AwesomeVersion("3.0.0")
        _LOGGER.debug("Detected firmware: %s", self._config["version"])

        current = get_awesome_version(self._config["version"])
        _LOGGER.debug("Using version: %s", current)

        try:
            if current >= cutoff:
                url = f"{base_url}ESP32_WiFi_V4.x/releases/latest"
            else:
                url = f"{base_url}ESP8266_WiFi_v2.x/releases/latest"
            _LOGGER.debug("Firmware check URL: %s", url)
        except AwesomeVersionCompareException:
            _LOGGER.debug("Non-semver firmware version detected.")
            return None

        try:
            session = self._get_session()
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
    ) -> dict[str, Any] | None:
        """Process a firmware check request with a given session."""
        http_method = getattr(session, method)
        _LOGGER.debug(
            "Connecting to %s using method %s",
            url,
            method,
        )
        async with http_method(url) as resp:
            _LOGGER.debug("Firmware check response status: %d", resp.status)
            if resp.status != 200:
                return None
            message = await resp.text()
            try:
                message = json.loads(message)
            except json.JSONDecodeError:
                _LOGGER.error("Failed to parse JSON response: %s", message)
                return None

            if not isinstance(message, dict):
                _LOGGER.debug(
                    "Invalid JSON response type from GitHub: %s", type(message)
                )
                return None

            _LOGGER.debug(
                "GitHub release metadata successfully fetched for version: %s",
                message.get("tag_name"),
            )

            # Match browser_download_url based on buildenv
            download_url = None
            buildenv = self._config.get("buildenv")
            assets = message.get("assets", [])

            if not buildenv:
                _LOGGER.debug(
                    "Cannot resolve firmware asset: missing buildenv in config."
                )
                assets = []
            elif not isinstance(assets, list):
                _LOGGER.debug("Invalid GitHub assets payload: %r", assets)
                assets = []
            else:
                _LOGGER.debug("Matching buildenv '%s' against assets", buildenv)
                target_filename = f"{buildenv}.bin"
                for asset in assets:
                    if not isinstance(asset, Mapping):
                        continue
                    if asset.get("name") == target_filename:
                        download_url = asset.get("browser_download_url")
                        _LOGGER.debug("Found matching firmware asset: %s", download_url)
                        break
            if buildenv and not download_url:
                _LOGGER.debug(
                    "Could not find asset matching target filename '%s.bin' in assets: %s",
                    buildenv,
                    [
                        asset.get("name")
                        for asset in assets
                        if isinstance(asset, Mapping)
                    ]
                    if assets
                    else "None",
                )

            return {
                "latest_version": message.get("tag_name"),
                "release_notes": message.get("body"),
                "release_url": message.get("html_url"),
                "browser_download_url": download_url,
            }

    async def update_firmware(
        self,
        firmware_url: str | None = None,
        firmware_bytes: bytes | None = None,
        filename: str = "firmware.bin",
    ) -> Mapping[str, Any] | list[Any] | str | bool:
        """Instruct the device to update its firmware.

        You can either:
        1. Pass firmware_bytes to perform a multipart upload of a local file.
        2. Pass firmware_url to tell the device to download the file directly.
        3. Pass neither to automatically resolve the latest matching binary URL from GitHub.
        """
        if not self._version_check("4.1.7"):
            _LOGGER.debug("Feature not supported for older firmware.")
            raise UnsupportedFeature

        if firmware_bytes is not None and firmware_url is not None:
            _LOGGER.error("Cannot specify both firmware_bytes and firmware_url")
            raise ValueError("Cannot specify both firmware_bytes and firmware_url")

        if firmware_bytes is not None and len(firmware_bytes) == 0:
            _LOGGER.error("Empty firmware bytes provided")
            raise ValueError("Empty firmware bytes provided")

        if firmware_url is not None:
            if not isinstance(firmware_url, str) or not firmware_url.strip():
                _LOGGER.error("Invalid firmware_url: %s", firmware_url)
                raise ValueError("Invalid firmware_url")

        url = f"{self.url}update"

        # 1. Handle multipart binary upload
        if firmware_bytes is not None:
            form_data = aiohttp.FormData()
            form_data.add_field(
                name="file",
                value=firmware_bytes,
                filename=filename,
                content_type="application/octet-stream",
            )
            _LOGGER.debug(
                "Uploading firmware binary to %s (%d bytes)", url, len(firmware_bytes)
            )
            # Rapi is mapped to http request's data kwarg in process_request
            response = await self.process_request(
                url=url, method="post", rapi=form_data
            )
            _LOGGER.debug("Firmware upload request completed. Response: %s", response)
            self._flag_ota_if_started(response)
            return response

        # 2. Resolve URL from GitHub if not specified
        if firmware_url is None:
            _LOGGER.debug(
                "No firmware URL provided. Resolving latest matching firmware from GitHub."
            )
            check_result = await self.firmware_check()
            if not check_result or not check_result.get("browser_download_url"):
                _LOGGER.error(
                    "Could not resolve latest firmware download URL from GitHub."
                )
                raise FirmwareResolutionError(
                    "Could not resolve latest firmware download URL from GitHub."
                )
            firmware_url = check_result["browser_download_url"]

        # 3. Post JSON URL payload
        data = {"url": firmware_url}
        _LOGGER.debug(
            "Requesting OpenEVSE to download and update from: %s", firmware_url
        )
        response = await self.process_request(url=url, method="post", data=data)
        _LOGGER.debug("Firmware update request completed. Response: %s", response)
        self._flag_ota_if_started(response)
        return response
