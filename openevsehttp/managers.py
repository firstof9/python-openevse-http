"""Manager methods (limits, claims) for the OpenEVSE charger."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from .const import CLIENT, RELEASE, TYPE, VALUE
from .exceptions import InvalidType, UnsupportedFeature

_LOGGER = logging.getLogger(__name__)


class ManagersMixin:
    """Mixin providing limit and claim management methods for OpenEVSE."""

    url: str

    # These are defined in client.py
    def _version_check(self, min_version: str, max_version: str = "") -> bool:
        raise NotImplementedError

    async def process_request(
        self, url: str, method: str = "", data: Any = None, rapi: Any = None
    ) -> Mapping[str, Any] | list[Any] | str:
        raise NotImplementedError

    def _normalize_response(self, response: Any) -> dict[str, Any] | list[Any]:
        """Normalize response to a dict or list."""
        raise NotImplementedError

    # Limit endpoint
    async def set_limit(
        self, limit_type: str, value: int, release: bool | None = None
    ) -> Any:
        """Set charge limit."""
        if not self._version_check("5.0.0"):
            _LOGGER.debug("Feature not supported for older firmware.")
            raise UnsupportedFeature

        url = f"{self.url}limit"
        data: dict[str, Any] = await self.get_limit()
        valid_types = ["time", "energy", "soc", "range"]

        if limit_type not in valid_types:
            raise InvalidType

        data[TYPE] = limit_type
        data[VALUE] = value
        if release is not None:
            data[RELEASE] = release

        _LOGGER.debug("Limit data: %s", data)
        _LOGGER.debug("Setting limit config on %s", url)
        response = await self.process_request(url=url, method="post", data=data)
        return self._normalize_response(response)

    async def clear_limit(self) -> Any:
        """Clear charge limit."""
        if not self._version_check("5.0.0"):
            _LOGGER.debug("Feature not supported for older firmware.")
            raise UnsupportedFeature

        url = f"{self.url}limit"

        _LOGGER.debug("Clearing limit config on %s", url)
        response = await self.process_request(url=url, method="delete")
        return self._normalize_response(response)

    async def get_limit(self) -> Any:
        """Get charge limit."""
        if not self._version_check("5.0.0"):
            _LOGGER.debug("Feature not supported for older firmware.")
            raise UnsupportedFeature

        url = f"{self.url}limit"

        _LOGGER.debug("Getting limit config on %s", url)
        response = await self.process_request(url=url, method="get")
        return self._normalize_response(response)

    async def make_claim(
        self,
        state: str | None = None,
        charge_current: int | None = None,
        max_current: int | None = None,
        auto_release: bool = True,
        client: int = CLIENT,
    ) -> Any:
        """Make a claim."""
        if not self._version_check("4.1.0"):
            _LOGGER.debug("Feature not supported for older firmware.")
            raise UnsupportedFeature

        if state not in ["active", "disabled", None]:
            _LOGGER.error("Invalid claim state: %s", state)
            raise ValueError

        url = f"{self.url}claims/{client}"

        data: dict[str, Any] = {}

        data["auto_release"] = auto_release

        if state is not None:
            data["state"] = state
        if charge_current is not None:
            data["charge_current"] = charge_current
        if max_current is not None:
            data["max_current"] = max_current

        _LOGGER.debug("Claim data: %s", data)
        _LOGGER.debug("Setting up claim on %s", url)
        response = await self.process_request(url=url, method="post", data=data)
        return self._normalize_response(response)

    async def release_claim(self, client: int = CLIENT) -> Any:
        """Delete a claim."""
        if not self._version_check("4.1.0"):
            _LOGGER.debug("Feature not supported for older firmware.")
            raise UnsupportedFeature

        url = f"{self.url}claims/{client}"

        _LOGGER.debug("Releasing claim on %s", url)
        response = await self.process_request(url=url, method="delete")
        return self._normalize_response(response)

    async def list_claims(self, target: bool | None = None) -> Any:
        """List all claims."""
        if not self._version_check("4.1.0"):
            _LOGGER.debug("Feature not supported for older firmware.")
            raise UnsupportedFeature

        target_check = ""
        if target:
            target_check = "/target"

        url = f"{self.url}claims{target_check}"

        _LOGGER.debug("Getting claims on %s", url)
        response = await self.process_request(url=url, method="get")
        return self._normalize_response(response)
