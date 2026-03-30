"""Limit class for OpenEVSE HTTP."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from .const import RELEASE, TYPE, VALUE
from .exceptions import InvalidType, UnsupportedFeature

if TYPE_CHECKING:
    from .client import OpenEVSE

_LOGGER = logging.getLogger(__name__)


class Limit:
    """Handle charge limits for OpenEVSE."""

    def __init__(self, evse: OpenEVSE) -> None:
        """Initialize the limit class."""
        self._evse = evse

    async def get(self) -> Any:
        """Get charge limit."""
        if not self._evse._version_check("5.0.0"):
            _LOGGER.debug("Feature not supported for older firmware.")
            raise UnsupportedFeature

        url = f"{self._evse.url}limit"

        _LOGGER.debug("Getting limit config on %s", url)
        response = await self._evse.process_request(url=url, method="get")
        return response

    async def set(
        self, limit_type: str, value: int, release: bool | None = None
    ) -> Any:
        """Set charge limit."""
        valid_types = ["time", "energy", "soc", "range"]

        if limit_type not in valid_types:
            raise InvalidType

        if not self._evse._version_check("5.0.0"):
            _LOGGER.debug("Feature not supported for older firmware.")
            raise UnsupportedFeature

        url = f"{self._evse.url}limit"
        data = {TYPE: limit_type, VALUE: value}
        if release is not None:
            data[RELEASE] = release

        _LOGGER.debug("Limit data: %s", data)
        _LOGGER.debug("Setting limit config on %s", url)
        response = await self._evse.process_request(url=url, method="post", data=data)
        return response

    async def clear(self) -> Any:
        """Clear charge limit."""
        if not self._evse._version_check("5.0.0"):
            _LOGGER.debug("Feature not supported for older firmware.")
            raise UnsupportedFeature

        url = f"{self._evse.url}limit"

        _LOGGER.debug("Clearing limit config on %s", url)
        response = await self._evse.process_request(url=url, method="delete")
        return response
